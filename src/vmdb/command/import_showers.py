import csv
import getopt
import json
import logging
import sys
import warnings
from vmdb.model import DBAdapter
from vmdb.command import CsvImport, ImportException


class ShowerImport(CsvImport):

    month_names = {
        None: None,
        'Jan': 1,
        'Feb': 2,
        'Mar': 3,
        'Apr': 4,
        'May': 5,
        'Jun': 6,
        'Jul': 7,
        'Aug': 8,
        'Sep': 9,
        'Oct': 10,
        'Nov': 11,
        'Dec': 12,
    }

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        self.required_columns = {
            'id',
            'iau_code',
            'name',
            'start',
            'end',
            'peak',
            'ra',
            'de',
            'v',
            'r',
            'zhr'
        }
        self.insert_stmt = db_conn.convert_stmt('''
            INSERT INTO shower (
                id,
                iau_code,
                "name",
                start_month,
                start_day,
                end_month,
                end_day,
                peak_month,
                peak_day,
                ra,
                "dec",
                v,
                r,
                zhr
            ) VALUES (
                %(id)s,
                %(iau_code)s,
                %(name)s,
                %(start_month)s,
                %(start_day)s,
                %(end_month)s,
                %(end_day)s,
                %(peak_month)s,
                %(peak_day)s,
                %(ra)s,
                %(dec)s,
                %(v)s,
                %(r)s,
                %(zhr)s
            )
        ''')

    def run(self, files_list):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS shower'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE shower (
                id integer NOT NULL,
                iau_code varchar(6) NOT NULL,
                name text NOT NULL,
                start_month integer NOT NULL,
                start_day integer NOT NULL,
                end_month integer NOT NULL,
                end_day integer NOT NULL,
                peak_month integer,
                peak_day integer,
                ra real,
                "dec" real,
                v real,
                r real,
                zhr real,
                CONSTRAINT shower_pkey PRIMARY KEY (id),
                CONSTRAINT shower_iau_code_ukey UNIQUE (iau_code)
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
                iau_code = self._parse_iau_code(row['iau_code'])
                ra = self._parse_ra(row['ra'], iau_code)
                dec = self._parse_dec(row['de'], iau_code)
                v = self._parse_velocity(row['v'], iau_code)
                r = self._parse_r_value(row['r'], iau_code)
                peak = self._create_date(row['peak'], 'peak', iau_code)
                period_start = self._create_date(row['start'], 'start', iau_code)
                period_end = self._create_date(row['end'], 'end', iau_code)

                if (ra is None) ^ (dec is None):
                    raise ImportException(
                        '%s: ra and dec must be set or both must be undefined.' % iau_code
                    )

            except ImportException as err:
                self._log_error(str(err))
                continue

            shower_name = row['name'].strip()
            if 0 == len(shower_name):
                self.logger.warning("%s: name of shower is empty." % iau_code)

            zhr = row['zhr'].strip()
            record = {
                'id': int(row['id'].strip()),
                'iau_code': iau_code,
                'name': shower_name,
                'start_month': period_start[0],
                'start_day': period_start[1],
                'end_month': period_end[0],
                'end_day': period_end[1],
                'peak_month': peak[0],
                'peak_day': peak[1],
                'ra': ra,
                'dec': dec,
                'v': v,
                'r': r,
                'zhr': zhr if '' != zhr else None,
            }
            cur.execute(self.insert_stmt, record)
            self.counter_write += 1

    @staticmethod
    def _parse_iau_code(rec):
        iau_code = rec.strip()
        if '' == iau_code:
            raise ImportException("Shower found without an iau_code.")

        return iau_code.upper()

    @staticmethod
    def _parse_velocity(rec, iau_code):
        v = rec.strip()
        if '' == v:
            return None

        try:
            v = float(v)
        except ValueError:
            raise ImportException("%s: invalid velocity value. The value is %s." % (iau_code, v))

        if v < 11 or v > 75:
            raise ImportException("%s: velocity must be between 11 and 75 instead of %s." % (iau_code, v))

        return v

    @staticmethod
    def _parse_r_value(rec, iau_code):
        r = rec.strip()
        if '' == r:
            return None

        try:
            r = float(r)
        except ValueError:
            raise ImportException("%s: invalid r-value. The value is %s." % (iau_code, r))

        if r < 1 or r > 5:
            raise ImportException("%s: r-value must be between 1 and 5 instead of %s." % (iau_code, r))

        return r

    @classmethod
    def _create_date(cls, date_str, ctx, iau_code):
        date_str = date_str.strip()

        if '' == date_str:
            return [None, None]

        month_names = cls.month_names
        value = date_str.split()

        if len(value) != 2:
            raise ImportException(
                "%s: %s must have the the format MM/DD. The value is %s." %
                (iau_code, ctx, value)
            )

        if value[0] not in month_names:
            raise ImportException("%s: %s is an invalid month name. The value is %s." % (iau_code, value[0], ctx))

        month = month_names[value[0]]

        try:
            day = int(value[1])
        except ValueError:
            raise ImportException("%s: %s is an invalid day. The value is %s." % (iau_code, value[1], ctx))

        return cls._validate_date(month, day, iau_code, ctx)


def usage():
    print('''Imports meteor showers.
Syntax: import_showers <options> csv_file
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
    imp = ShowerImport(db_conn, logger)
    imp.run(args)
    db_conn.close()

    if imp.has_errors:
        print('Errors occurred when importing showers.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
