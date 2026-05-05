import csv
import sys
from optparse import OptionParser, Values
from typing import IO

from imo_vmdb import export_table
from imo_vmdb.command import config_factory
from imo_vmdb.db import DBAdapter, DBException

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

ALL_TABLES = list(DB_TABLES)


def main(command_args: list[str]) -> None:
    """Parse arguments and run the CSV export command.

    :param command_args: CLI argument list (typically ``sys.argv[1:]``).
    """
    parser = OptionParser(
        usage="export <table> [options]\n\nTables: " + ", ".join(ALL_TABLES)
    )
    parser.add_option(
        "-c", action="store", dest="config_file", help="path to config file"
    )
    parser.add_option(
        "-o",
        action="store",
        dest="output_file",
        metavar="FILE",
        help="output file (default: stdout)",
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

    table = args[0]
    if table not in ALL_TABLES:
        print(
            f'Unknown table: {table!r}. Valid tables: {", ".join(ALL_TABLES)}',
            file=sys.stderr,
        )
        sys.exit(1)

    out = (
        open(options.output_file, "w", newline="", encoding="utf-8")
        if options.output_file
        else sys.stdout
    )

    try:
        _export_db(table, options, parser, out, reimport=options.reimport)
    finally:
        if options.output_file:
            out.close()


def _export_db(
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
    try:
        config = config_factory(options, parser)
    except SystemExit:
        raise

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
