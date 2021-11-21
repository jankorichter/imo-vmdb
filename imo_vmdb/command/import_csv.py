import csv
import sys
from optparse import OptionParser
from imo_vmdb.command import config_factory, LoggerFactory
from imo_vmdb.csv_import.magnitudes import MagnitudesParser
from imo_vmdb.csv_import.rate import RateParser
from imo_vmdb.csv_import.radiant import RadiantParser
from imo_vmdb.csv_import.shower import ShowerParser
from imo_vmdb.csv_import.session import SessionParser
from imo_vmdb.db import DBAdapter, DBException


class CSVFileException(Exception):
    pass


class CSVParserException(Exception):
    pass


class CSVImport(object):
    csv_parser = {
        MagnitudesParser,
        RateParser,
        ShowerParser,
        SessionParser,
        RadiantParser
    }

    def __init__(self, db_conn, log_factory, do_delete=False, try_repair=False, is_permissive=False):
        self._db_conn = db_conn
        self._log_factory = log_factory
        self._logger = log_factory.get_logger('import_csv')
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

        cur.close()
        self._db_conn.commit()
        self._logger.info(
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
        args = (self._db_conn, self._log_factory)
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


def main(command_args):
    parser = OptionParser(usage='import_csv [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    parser.add_option('-d', action='store_true', dest='delete', default=False,
                      help='deletes previously imported data')
    parser.add_option('-p', action='store_true', dest='permissive', default=False,
                      help='does not apply stringent tests')
    parser.add_option('-r', action='store_true', dest='repair', default=False,
                      help='an attempt is made to correct errors')
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)

    kwargs = {
        'do_delete': options.delete,
        'is_permissive': options.permissive,
        'try_repair': options.repair
    }

    try:
        db_conn = DBAdapter(config['database'])
        csv_import = CSVImport(db_conn, logger_factory, **kwargs)
        csv_import.run(args)
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    if csv_import.has_errors:
        print('Errors or warnings occurred when importing data.', file=sys.stderr)
        if logger_factory.log_file is not None:
            print('See log file %s for more information.' % logger_factory.log_file, file=sys.stderr)
        sys.exit(4)
