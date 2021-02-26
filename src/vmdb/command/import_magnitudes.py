import csv
import getopt
import json
import logging
import math
import sys
import warnings
from datetime import timedelta
from vmdb.model import DBAdapter
from vmdb.command import CsvImport, ImportException


class MagnImport(CsvImport):

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        self.required_columns = {
            'magnitude id',
            'user id',
            'obs session id',
            'shower',
            'start date',
            'end date',
            'mag n6',
            'mag n5',
            'mag n4',
            'mag n3',
            'mag n2',
            'mag n1',
            'mag 0',
            'mag 1',
            'mag 2',
            'mag 3',
            'mag 4',
            'mag 5',
            'mag 6',
            'mag 7'
        }
        self.insert_stmt = db_conn.convert_stmt('''
            INSERT INTO imported_magnitude (
                id,
                session_id,
                shower,
                "start",
                "end",
                user_id,
                magn
            ) VALUES (
                %(id)s,
                %(session_id)s,
                %(shower)s,
                %(start)s,
                %(end)s,
                %(user_id)s,
                %(magn)s
            )
        ''')

    def run(self, files_list):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_magnitude'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_magnitude
            (
                id integer NOT NULL,
                session_id integer NOT NULL,
                shower varchar(6) NULL,
                "start" timestamp NOT NULL,
                "end" timestamp NOT NULL,
                user_id integer NULL,
                magn text NOT NULL,
                CONSTRAINT imported_magnitude_pkey PRIMARY KEY (id)
            )
        '''))

        super()._parse_csv_files(cur, files_list)

        cur.execute(db_conn.convert_stmt('''
            CREATE INDEX imported_magnitude_order_key ON
                imported_magnitude(
                    session_id,
                    shower,
                    "start",
                    "end"
                )
        '''))

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
                magn_id = self._parse_magn_id(row['magnitude id'])
                session_id = self._parse_session_id(row['obs session id'], magn_id)
                shower = self._parse_shower(row['shower'])
                user_id = self._parse_observer_id(row['user id'], 'user id', magn_id)
                period_start = self._parse_date_time(row['start date'], 'start date', magn_id)
                period_end = self._parse_date_time(row['end date'], 'end date', magn_id)
                period_start, period_end = self._check_period(
                    period_start,
                    period_end,
                    timedelta(0.49),
                    magn_id
                )
            except ImportException as err:
                self._log_error(str(err))
                continue

            magn = {}
            try:
                for column in range(1, 7):
                    n = float(row['mag n' + str(column)])
                    magn[str(-column)] = n

                for column in range(0, 8):
                    n = float(row['mag ' + str(column)])
                    magn[str(column)] = n
            except ValueError:
                self._log_error('%s: Invalid count value of magnitudes found.' % magn_id)
                continue

            try:
                for m, n in magn.items():
                    self._validate_count(n, m, magn_id)
                self._validate_total_count(magn, magn_id)
            except ImportException as err:
                self._log_error(str(err))
                continue

            freq = int(sum(n for n in magn.values()))
            if 0 == freq:
                continue

            magn = json.dumps({m: n for m, n in magn.items() if n > 0})

            record = {
                'id': magn_id,
                'session_id': session_id,
                'shower': shower,
                'start': period_start,
                'end': period_end,
                'user_id': user_id,
                'magn': magn
            }
            cur.execute(self.insert_stmt, record)
            self.counter_write += 1

    @staticmethod
    def _parse_magn_id(rec):
        magn_id = rec.strip()
        if '' == magn_id:
            raise ImportException("Observation found without a magnitude id.")

        try:
            magn_id = int(magn_id)
        except ValueError:
            raise ImportException("%s: invalid magnitude id." % magn_id)
        if magn_id < 1:
            raise ImportException("%s: magnitude id must be greater than 0." % magn_id)

        return magn_id

    @staticmethod
    def _validate_count(n, m, magn_id):
        if n < 0.0:
            raise ImportException(
                "%s: Invalid count %s found for a meteor magnitude of %s." %
                (magn_id, n, m)
            )

        n_cmp = math.floor(n)
        if n == n_cmp:
            return

        n_cmp += 0.5
        if n == n_cmp:
            return

        raise ImportException(
            "%s: Invalid count %s found for a meteor magnitude of %s." %
            (magn_id, n, m))

    @staticmethod
    def _validate_total_count(magn, magn_id):
        n_sum = 0
        for m in sorted(magn.keys(), key=int):
            n = magn[m]
            n_sum += n
            if 0 == n and math.floor(n_sum) != n_sum:
                raise ImportException("%s: Inconsistent total count of meteors found." % magn_id)

        if math.floor(n_sum) != n_sum:
            raise ImportException(
                "%s: The count of meteors out of a total of %s is invalid." %
                (magn_id, n_sum)
            )


def usage():
    print('''Imports magnitude observations.
Syntax: import_magnitudes <options> files ...
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

    if len(args) < 1:
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
                format='%(asctime)s [%(levelname)s] %(message)s',
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
    imp = MagnImport(db_conn, logger)
    imp.run(args)
    db_conn.close()

    if imp.has_errors:
        print('Errors occurred when importing magnitude observations.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
