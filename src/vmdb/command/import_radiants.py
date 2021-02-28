import csv
import getopt
import json
import logging
import sys
import warnings
from vmdb.model import DBAdapter
from vmdb.command import CsvImport, ImportException


class RadiantImport(CsvImport):

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        self.required_columns = {
            'shower',
            'ra',
            'dec',
            'day',
            'month'
        }
        self.insert_stmt = db_conn.convert_stmt('''
            INSERT INTO radiant (
                shower,
                ra,
                "dec",
                "month",
                "day"
            ) VALUES (
                %(shower)s,
                %(ra)s,
                %(dec)s,
                %(month)s,
                %(day)s
            )
        ''')

    def run(self, files_list):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS radiant'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE radiant
            (
                shower char(3) NOT NULL,
                "month" integer NOT NULL,
                "day" integer NOT NULL,
                ra real NOT NULL,
                "dec" real NOT NULL,
                CONSTRAINT radiant_pkey PRIMARY KEY (shower, "month", "day")
            )
        '''))

        super()._parse_csv_files(cur, files_list)
        super()._commit(cur)

    def _parse_csv_file(self, cur, csv_file):
        csv_reader = csv.reader(csv_file, delimiter=';')
        is_head = True
        column_names = []
        for row in csv_reader:
            if is_head:
                is_head = False
                column_names = self._get_column_names(row)
                if column_names is None:
                    return

                continue

            self.counter_read += 1
            row = dict(zip(column_names, row))

            try:
                shower = self._parse_shower(row['shower'])
                ra = self._parse_ra(row['ra'], shower)
                dec = self._parse_dec(row['dec'], shower)
                month = self._parse_int(row['month'], 'month', shower)
                day = self._parse_int(row['day'], 'day', shower)
                self._validate_date(month, day, shower)
                if ra is None or dec is None:
                    raise ImportException('%s: ra and dec must be set.' % shower)

            except ImportException as err:
                self._log_error(str(err))
                continue

            record = {
                'shower': shower,
                'ra': ra,
                'dec': dec,
                'month': month,
                'day': day,
            }
            cur.execute(self.insert_stmt, record)
            self.counter_write += 1

    @staticmethod
    def _parse_shower(rec):
        shower = rec.strip()
        if '' == shower:
            raise ImportException("Shower code must not be empty.")

        return shower.upper()

    @staticmethod
    def _parse_int(rec, ctx, iau_code):
        value = rec.strip()

        try:
            value = int(value)
        except ValueError:
            raise ImportException("%s: %s is an invalid %s." % (iau_code, value, ctx))

        return value


def usage():
    print('''Imports radiant positions.
Syntax: import_radiants <options> radiants.csv
    options
        -c, --config ... path to config file
        -l, --log    ... path to log file
        -h, --help   ... prints this help''')


def main(command_args):
    config = None

    try:
        opts, args = getopt.getopt(command_args, "hc:l:", ['help', 'config', 'log'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 1:
        usage()
        sys.exit(1)

    logger = logging.getLogger()
    logger.disabled = True
    log_file = None

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--config"):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        elif o in ("-l", "--log"):
            log_file = a
            logging.basicConfig(
                filename=log_file,
                format='%(asctime)s import_radiants[%(levelname)s] %(message)s',
                level=logging.INFO
            )
            logger.disabled = False
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    db_conn = DBAdapter(config['database'])
    imp = RadiantImport(db_conn, logger)
    imp.run(args)
    db_conn.close()

    if imp.has_errors:
        print('Errors occurred when importing radiant positions.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
