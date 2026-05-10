import csv
import sqlite3
import sys
from optparse import OptionParser, Values
from typing import IO

from imo_vmdb import DBAdapter, DBException, export_db, export_table
from imo_vmdb.command import config_factory

REIMPORT_TABLES = {"shower", "radiant"}

DB_TABLES = {
    "shower": "shower",
    "radiant": "radiant",
    "session": "obs_session",
    "rate": "rate",
    "magnitude": "magnitude",
    "magnitude_detail": "magnitude_detail",
    "rate_magnitude": "rate_magnitude",
}

DB_TARGET = "db"

ALL_TARGETS = list(DB_TABLES) + [DB_TARGET]


def main(command_args: list[str]) -> None:
    """Parse arguments and run the export command.

    Supports two output modes:

    * ``<table>`` — export a single table as semicolon-delimited CSV
      (to ``-o`` or stdout).
    * ``db`` — export the whole database as a SQLite file (``-o`` required).

    :param command_args: CLI argument list (typically ``sys.argv[1:]``).
    """
    parser = OptionParser(
        usage=(
            "export <target> [options]\n\n"
            "Targets:\n"
            "  " + ", ".join(DB_TABLES) + "\n"
            "    Export a single table as semicolon-delimited CSV.\n"
            "  db\n"
            "    Export the whole database as a SQLite file (-o required)."
        )
    )
    parser.add_option(
        "-c", action="store", dest="config_file", help="path to config file"
    )
    parser.add_option(
        "-o",
        action="store",
        dest="output_file",
        metavar="FILE",
        help="output file (default: stdout for CSV; required for db)",
    )
    parser.add_option(
        "--reimport",
        action="store_true",
        dest="reimport",
        default=False,
        help="export in original import format (shower and radiant only)",
    )
    options, args = parser.parse_args(command_args)

    if not args:
        parser.print_help()
        sys.exit(1)

    target = args[0]
    if target not in ALL_TARGETS:
        print(
            f"Unknown target: {target!r}. Valid targets: {', '.join(ALL_TARGETS)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if target == DB_TARGET:
        if options.reimport:
            parser.error("--reimport is not supported with target 'db'")
        if not options.output_file:
            parser.error("-o is required when exporting the database (target 'db')")
        _export_database(options, parser)
        return

    out = (
        open(options.output_file, "w", newline="", encoding="utf-8")
        if options.output_file
        else sys.stdout
    )

    try:
        _export_table_to_csv(target, options, parser, out, reimport=options.reimport)
    finally:
        if options.output_file:
            out.close()


def _export_table_to_csv(
    table: str,
    options: Values,
    parser: OptionParser,
    out: IO[str],
    reimport: bool = False,
) -> None:
    """Connect to the database, export *table*, and write semicolon-delimited CSV to *out*.

    :param table: Logical table name (key in :data:`DB_TABLES`).
    :param options: Parsed options object with a ``config_file`` attribute.
    :param parser: CLI parser used to print usage on configuration errors.
    :param out: Writable text stream to receive the CSV output.
    :param reimport: If ``True``, export in reimport-compatible format.
    """
    config = config_factory(options, parser)

    try:
        db_conn = DBAdapter(dict(config["database"]))
        cols, rows = export_table(db_conn, DB_TABLES[table], reimport=reimport)
        db_conn.close()
    except DBException as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(100)

    writer = csv.writer(out, delimiter=";")
    writer.writerow(cols)
    writer.writerows(rows)


def _export_database(options: Values, parser: OptionParser) -> None:
    """Export the whole database as a SQLite file at ``options.output_file``.

    :param options: Parsed options object with ``config_file`` and
        ``output_file`` attributes.
    :param parser: CLI parser used to print usage on configuration errors.
    """
    config = config_factory(options, parser)

    try:
        src = DBAdapter(dict(config["database"]))
    except DBException as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(100)

    try:
        dst_conn = sqlite3.connect(options.output_file)
        try:
            export_db(src, dst_conn)
        finally:
            dst_conn.close()
    except DBException as e:
        print(f"Database error: {e}", file=sys.stderr)
        sys.exit(100)
    finally:
        src.close()
