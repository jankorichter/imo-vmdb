import csv
import os
import imo_vmdb.command.cleanup
import imo_vmdb.command.import_csv
import imo_vmdb.command.initdb
import imo_vmdb.command.normalize
from imo_vmdb.csv_import.magnitudes import MagnitudesParser
from imo_vmdb.csv_import.rate import RateParser
from imo_vmdb.csv_import.radiant import RadiantParser
from imo_vmdb.csv_import.shower import ShowerParser
from imo_vmdb.csv_import.session import SessionParser
from imo_vmdb.model.radiant import Storage as RadiantStorage
from imo_vmdb.model.shower import Storage as ShowerStorage
from imo_vmdb.model.sky import Sky
from imo_vmdb.normalizer import create_rate_magn
from imo_vmdb.normalizer.magnitude import MagnitudeNormalizer
from imo_vmdb.normalizer.rate import RateNormalizer
from imo_vmdb.normalizer.session import SessionNormalizer
from pathlib import Path
from imo_vmdb.db import create_tables

_cli_cleanup = imo_vmdb.command.cleanup.main
_cli_import_csv = imo_vmdb.command.import_csv.main
_cli_initdb = imo_vmdb.command.initdb.main
_cli_normalize = imo_vmdb.command.normalize.main


class CSVFileException(Exception):
    pass


class CSVParserException(Exception):
    pass


class CSVImporter(object):
    csv_parser = {
        MagnitudesParser,
        RateParser,
        ShowerParser,
        SessionParser,
        RadiantParser
    }

    def __init__(self, db_conn, logger, do_delete=False, try_repair=False, is_permissive=False):
        self._db_conn = db_conn
        self._logger = logger
        self._do_delete = do_delete
        self._is_permissive = is_permissive
        self._try_repair = try_repair
        self._active_parsers = []
        self.counter_read = 0
        self.counter_write = 0
        self.has_errors = False

    def run(self, files_list):
        db_conn = self._db_conn
        logger = self._logger
        cur = db_conn.cursor()

        for file_path in files_list:

            logger.info('Start parsing the data from file %s.' % file_path)

            try:
                with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
                    self._parse_csv_file(csv_file, cur)
            except FileNotFoundError:
                self._log_critical('The file %s could not be found.' % file_path)
                continue
            except IsADirectoryError:
                self._log_critical('The file %s is a directory.' % file_path)
                continue
            except PermissionError:
                self._log_critical('File %s could not be opened.' % file_path)
                continue
            except CSVFileException:
                self._log_critical('File %s seems not to be a valid CSV file.' % file_path)
                continue
            except CSVParserException:
                self._log_critical('File %s is an unknown CSV file.' % file_path)
                continue

            logger.info(
                'Parsing of file %s has finished.' % file_path
            )

        for csv_parser in self._active_parsers:
            csv_parser.on_shutdown(cur)
            if csv_parser.has_errors:
                self.has_errors = True

        logger.info(
            'Parsing of the files has finished. %s of %s records were imported.' %
            (self.counter_write, self.counter_read)
        )

    def _log_critical(self, msg):
        self._logger.critical(msg)
        self.has_errors = True

    def _parse_csv_file(self, csv_file, cur):
        try:
            csv_reader = csv.reader(csv_file, delimiter=';')
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
        args = (self._db_conn, self._logger)
        kwargs = {
            'do_delete': self._do_delete,
            'is_permissive': self._is_permissive,
            'try_repair': self._try_repair
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


def cleanup(db_conn, logger):
    logger.info('Starting cleaning up the database.')
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt('DELETE FROM imported_magnitude'))
    cur.execute(db_conn.convert_stmt('DELETE FROM imported_rate'))
    cur.execute(db_conn.convert_stmt('DELETE FROM imported_session'))
    cur.close()
    logger.info('Cleanup of the database completed.')

    return 0


def initdb(db_conn, logger):
    my_dir = Path(os.path.dirname(os.path.realpath(__file__)))
    shower_file = str(my_dir / 'data' / 'showers.csv')
    radiants_file = str(my_dir / 'data' / 'radiants.csv')
    logger.info('Starting initialization of the database.')
    create_tables(db_conn)
    logger.info('Database initialized.')
    csv_import = CSVImporter(db_conn, logger, do_delete=True)
    csv_import.run((shower_file, radiants_file))

    return int(csv_import.has_errors)


def normalize(db_conn, logger):
    logger.info('Starting normalization of the sessions.')
    sn = SessionNormalizer(db_conn, logger)
    sn.run()
    logger.info(
        'The normalisation of the sessions has been completed. %s of %s records have been written.' %
        (sn.counter_write, sn.counter_read)
    )

    logger.info('Start of normalization the rates.')
    radiant_storage = RadiantStorage(db_conn)
    radiants = radiant_storage.load()
    shower_storage = ShowerStorage(db_conn)
    showers = shower_storage.load(radiants)
    sky = Sky()
    rn = RateNormalizer(db_conn, logger, sky, showers)
    rn.run()
    logger.info(
        'The normalisation of the rates has been completed. %s of %s records have been written.' %
        (rn.counter_write, rn.counter_read)
    )

    logger.info('Start of normalization the magnitudes.')
    mn = MagnitudeNormalizer(db_conn, logger, sky)
    mn.run()
    logger.info(
        'The normalisation of the magnitudes has been completed. %s of %s records have been written.' %
        (rn.counter_write, rn.counter_read)
    )

    logger.info('Start creating rate magnitude relationship.')
    create_rate_magn(db_conn)
    logger.info('The relationship between rate and magnitude was created.')
    logger.info('Normalisation completed.')

    if rn.has_errors:
        return 1

    if mn.has_errors:
        return 2

    return 0
