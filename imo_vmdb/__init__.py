import csv
import logging
import os
from pathlib import Path

from imo_vmdb.csv_import.magnitudes import MagnitudesParser
from imo_vmdb.csv_import.radiant import RadiantParser
from imo_vmdb.csv_import.rate import RateParser
from imo_vmdb.csv_import.session import SessionParser
from imo_vmdb.csv_import.shower import ShowerParser
from imo_vmdb.db import DBAdapter, create_tables
from imo_vmdb.model.radiant import Storage as RadiantStorage
from imo_vmdb.model.shower import Storage as ShowerStorage
from imo_vmdb.model.sky import Sky
from imo_vmdb.normalizer import create_rate_magn
from imo_vmdb.normalizer.magnitude import MagnitudeNormalizer
from imo_vmdb.normalizer.rate import RateNormalizer
from imo_vmdb.normalizer.session import SessionNormalizer
from imo_vmdb.query import (
    Magnitude,
    MagnitudeDetail,
    MagnitudeFilter,
    Magnitudes,
    Rate,
    RateFilter,
    Rates,
    Session,
    Shower,
    query_magnitudes,
    query_rates,
    query_showers,
)

__all__ = [
    "CSVImporter",
    "DBAdapter",
    "Magnitude",
    "MagnitudeDetail",
    "MagnitudeFilter",
    "Magnitudes",
    "Rate",
    "RateFilter",
    "Rates",
    "Session",
    "Shower",
    "cleanup",
    "export_table",
    "initdb",
    "normalize",
    "query_magnitudes",
    "query_rates",
    "query_showers",
]

_MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

_VALID_TABLES = frozenset(
    {
        "shower",
        "radiant",
        "obs_session",
        "imported_session",
        "imported_rate",
        "imported_magnitude",
        "rate",
        "magnitude",
        "rate_magnitude",
        "magnitude_detail",
    }
)


def _format_date(month: int | None, day: int | None) -> str:
    """Format a month/day pair as an abbreviated month name and day number.

    :param month: Month as an integer (1–12), or ``None``.
    :param day: Day as an integer, or ``None``.
    :return: Formatted string such as ``'Aug 12'``, or an empty string if
        either value is ``None``.
    """
    if month is None or day is None:
        return ""
    return f"{_MONTH_NAMES[month]} {day}"


def export_table(
    db_conn: DBAdapter, table: str, reimport: bool = False
) -> tuple[list[str], list[tuple]]:
    """Export all rows from a database table.

    When *reimport* is ``True`` and *table* is ``'shower'``, the result uses
    column names and date formats that are compatible with :class:`CSVImporter`,
    so the exported CSV can be imported again without modification.  For all
    other tables *reimport* has no effect.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param table: Name of the table to export.  Must be one of the known
        tables: ``shower``, ``radiant``, ``obs_session``, ``imported_session``,
        ``imported_rate``, ``imported_magnitude``, ``rate``, ``magnitude``,
        ``rate_magnitude``, ``magnitude_detail``.
    :param reimport: If ``True``, export in re-import-compatible format where applicable.
    :return: Tuple of ``(column_names, rows)``.
    :raises ValueError: If *table* is not a known table name.
    """
    if table not in _VALID_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    if reimport and table == "shower":
        return _export_shower_reimport(db_conn)
    cur = db_conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


def _export_shower_reimport(db_conn: DBAdapter) -> tuple[list[str], list[tuple]]:
    """Export the ``shower`` table in a format compatible with :class:`CSVImporter`.

    Converts start/end/peak month–day pairs into ``'Mon DD'`` strings and
    renames the ``dec`` column to ``de`` to match the import CSV schema.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :return: Tuple ``(column_names, rows)`` ready for CSV serialisation.
    """
    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, iau_code, name, start_month, start_day, end_month, end_day,"
        ' peak_month, peak_day, ra, "dec", v, r, zhr FROM shower ORDER BY id'
    )
    raw_rows = cur.fetchall()
    cols = [
        "id",
        "iau_code",
        "name",
        "start",
        "end",
        "peak",
        "ra",
        "de",
        "v",
        "r",
        "zhr",
    ]
    rows = [
        (
            id_,
            iau_code,
            name,
            _format_date(start_m, start_d),
            _format_date(end_m, end_d),
            _format_date(peak_m, peak_d),
            ra,
            dec,
            v,
            r,
            zhr,
        )
        for id_, iau_code, name, start_m, start_d, end_m, end_d, peak_m, peak_d, ra, dec, v, r, zhr in raw_rows
    ]
    return cols, rows


class CSVFileException(Exception):
    pass


class CSVParserException(Exception):
    pass


class CSVImporter:
    """
    A class for importing CSV files of various types into a database.

    The `CSVImporter` class allows to import CSV files into a database.
    You can specify whether to delete existing data, attempt data repair,
    or be permissive about non-critical data errors during the import.

    :param db_conn: An existing database connection implementing DB-API 2.0.
    :param logger: A logger object used to log errors, warnings, and additional information.
    :type logger: logging.Logger
    :param do_delete: If True, delete existing data before importing. Default is False.
    :type do_delete: bool
    :param try_repair: If True, attempt data repair during import. Default is False.
    :type try_repair: bool
    :param is_permissive: If True, be permissive about non-critical data errors. Default is False.
    :type is_permissive: bool
    """

    csv_parser = {
        MagnitudesParser,
        RateParser,
        ShowerParser,
        SessionParser,
        RadiantParser,
    }

    def __init__(
        self,
        db_conn: DBAdapter,
        logger: logging.Logger,
        do_delete: bool = False,
        try_repair: bool = False,
        is_permissive: bool = False,
    ) -> None:
        self._db_conn = db_conn
        self._logger = logger
        self._do_delete = do_delete
        self._is_permissive = is_permissive
        self._try_repair = try_repair
        self._active_parsers = []
        self.counter_read = 0
        self.counter_write = 0
        self.has_errors = False

    def run(self, file_list: list[str]) -> None:
        """
        Import CSV files specified in the files_list into the database.

        This method imports CSV files into the database, with options to delete existing data,
        attempt data repair, and be permissive about non-critical data errors.
        After running this method, you can check the `has_errors`, `counter_read`, and `counter_write`
        properties of this object to determine the import result.

        :param file_list: A list of file paths to CSV files for import.
        :type file_list: list of str
        """
        db_conn = self._db_conn
        logger = self._logger
        cur = db_conn.cursor()

        for file_path in file_list:
            logger.info("Start parsing the data from file %s." % file_path)

            try:
                with open(file_path, encoding="utf-8-sig") as csv_file:
                    self._parse_csv_file(csv_file, cur)
            except FileNotFoundError:
                self._log_critical("The file %s could not be found." % file_path)
                continue
            except IsADirectoryError:
                self._log_critical("The file %s is a directory." % file_path)
                continue
            except PermissionError:
                self._log_critical("File %s could not be opened." % file_path)
                continue
            except CSVFileException:
                self._log_critical(
                    "File %s seems not to be a valid CSV file." % file_path
                )
                continue
            except CSVParserException:
                self._log_critical("File %s is an unknown CSV file." % file_path)
                continue

            logger.info("Parsing of file %s has finished." % file_path)

        for csv_parser in self._active_parsers:
            csv_parser.on_shutdown(cur)
            if csv_parser.has_errors:
                self.has_errors = True

        logger.info(
            "Parsing of the files has finished. %s of %s records imported, %s discarded."
            % (
                self.counter_write,
                self.counter_read,
                self.counter_read - self.counter_write,
            )
        )

    def _log_critical(self, msg: str) -> None:
        self._logger.critical(msg)
        self.has_errors = True

    def _parse_csv_file(self, csv_file, cur):
        """Parse a single open CSV file, routing each row to the appropriate parser.

        :param csv_file: Open text file object for the CSV file.
        :param cur: Open database cursor passed to the parser's row handler.
        :raises CSVFileException: If the CSV reader cannot be initialised.
        :raises CSVParserException: If no parser recognises the file's columns.
        """
        try:
            csv_reader = csv.reader(csv_file, delimiter=";")
        except Exception:
            raise CSVFileException()

        csv_parser = None
        is_head = True
        for row in csv_reader:
            if is_head:
                is_head = False
                csv_parser = self._create_csv_parser(row)
                if csv_parser is None:
                    raise CSVParserException()
                if csv_parser not in self._active_parsers:
                    self._active_parsers.append(csv_parser)
                    csv_parser.on_start(cur)
                continue

            self.counter_read += 1
            if csv_parser.parse_row(row, cur):
                self.counter_write += 1

    def _create_csv_parser(self, row):
        """Return the parser responsible for the CSV file identified by *row*.

        Re-uses an already active parser of the same type if one exists.

        :param row: Header row of the CSV file as a list of strings.
        :return: Initialised :class:`~imo_vmdb.csv_import.CsvParser` subclass
            instance, or ``None`` if no registered parser recognises the columns.
        """
        args = (self._db_conn, self._logger)
        kwargs = {
            "do_delete": self._do_delete,
            "is_permissive": self._is_permissive,
            "try_repair": self._try_repair,
        }

        column_names = [r.lower() for r in row]
        found_parser_cls = None
        for csv_parser_cls in self.csv_parser:
            if csv_parser_cls.is_responsible(column_names):
                found_parser_cls = csv_parser_cls
                break

        if found_parser_cls is None:
            return None

        for csv_parser in self._active_parsers:
            if isinstance(csv_parser, found_parser_cls):
                return csv_parser

        csv_parser = found_parser_cls(*args, **kwargs)
        csv_parser.column_names = column_names

        return csv_parser


def cleanup(db_conn: DBAdapter, logger: logging.Logger) -> int:
    """
    Remove all previously imported data, if any, while preserving normalized data in the database.

    This function takes an existing database connection and a logger object as parameters. It removes all
    previously imported data from the database, leaving normalized data intact.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param logger: A logger object used to log errors, warnings, and additional information.
    :type logger: logging.Logger
    :return: An integer indicating the result of the operation. 0 for success, other values for errors.
    :rtype: int
    """
    logger.info("Starting cleaning up the database.")
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt("DELETE FROM imported_magnitude"))
    cur.execute(db_conn.convert_stmt("DELETE FROM imported_rate"))
    cur.execute(db_conn.convert_stmt("DELETE FROM imported_session"))
    cur.close()
    logger.info("Cleanup of the database completed.")

    return 0


def initdb(db_conn: DBAdapter, logger: logging.Logger) -> int:
    """
    Initialize an empty database, removing all data if the database already exists.

    This function takes an existing database connection and a logger object as parameters.
    It initializes an empty database, removing all data if the database already exists.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param logger: A logger object used to log errors, warnings, and additional information.
    :type logger: logging.Logger
    :return: An integer indicating the result of the operation. 0 for success, 1 for errors.
    :rtype: int
    """
    my_dir = Path(os.path.dirname(os.path.realpath(__file__)))
    shower_file = str(my_dir / "data" / "showers.csv")
    radiants_file = str(my_dir / "data" / "radiants.csv")
    logger.info("Starting initialization of the database.")
    create_tables(db_conn)
    logger.info("Database initialized.")
    csv_import = CSVImporter(db_conn, logger, do_delete=True)
    csv_import.run((shower_file, radiants_file))

    return int(csv_import.has_errors)


def normalize(db_conn: DBAdapter, logger: logging.Logger) -> int:
    """
    Establish relationships between imported records and enrich observations with additional information.

    This function takes an existing database connection and a logger object as parameters. It establishes
    relationships between the imported records in the database, enriching observations with additional information.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param logger: A logger object used to log errors, warnings, and additional information.
    :type logger: logging.Logger
    :return: An integer indicating the result of the operation. 0 for success, 1 for errors.
    :rtype: int
    """
    logger.info("Starting normalization of the sessions.")
    sn = SessionNormalizer(db_conn, logger)
    sn.run()
    logger.info(
        "The normalisation of the sessions has been completed. %s of %s records written, %s discarded."
        % (sn.counter_write, sn.counter_read, sn.counter_discard)
    )

    logger.info("Start of normalization the rates.")
    radiant_storage = RadiantStorage(db_conn)
    radiants = radiant_storage.load()
    shower_storage = ShowerStorage(db_conn)
    showers = shower_storage.load(radiants)
    sky = Sky()
    rn = RateNormalizer(db_conn, logger, sky, showers)
    rn.run()
    logger.info(
        "The normalisation of the rates has been completed. %s of %s records written, %s discarded."
        % (rn.counter_write, rn.counter_read, rn.counter_discard)
    )

    logger.info("Start of normalization the magnitudes.")
    mn = MagnitudeNormalizer(db_conn, logger, sky)
    mn.run()
    logger.info(
        "The normalisation of the magnitudes has been completed. %s of %s records written, %s discarded."
        % (mn.counter_write, mn.counter_read, mn.counter_discard)
    )

    logger.info("Start creating rate magnitude relationship.")
    create_rate_magn(db_conn)
    logger.info("The relationship between rate and magnitude was created.")
    logger.info("Normalisation completed.")

    if sn.has_errors:
        return 1

    if rn.has_errors:
        return 1

    if mn.has_errors:
        return 1

    return 0
