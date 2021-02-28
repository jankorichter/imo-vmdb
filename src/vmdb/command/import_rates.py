import csv
import getopt
import json
import logging
import sys
import warnings
from datetime import timedelta
from vmdb.model import DBAdapter
from vmdb.command import CsvImport, ImportException


class RateImport(CsvImport):

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        self.required_columns = {
            'rate id',
            'user id',
            'obs session id',
            'start date',
            'end date',
            'ra',
            'decl',
            'teff',
            'f',
            'lm',
            'shower',
            'method',
            'number'
        }
        self.insert_stmt = db_conn.convert_stmt('''
            INSERT INTO imported_rate (
                id,
                user_id,
                session_id,
                "start",
                "end",
                t_eff,
                f,
                lm,
                shower,
                method,
                "number"
            ) VALUES (
                %(id)s,
                %(user_id)s,
                %(session_id)s,
                %(start)s,
                %(end)s,
                %(t_eff)s,
                %(f)s,
                %(lm)s,
                %(shower)s,
                %(method)s,
                %(number)s
            )
        ''')

    def run(self, files_list):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_rate'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_rate
            (
                id integer NOT NULL,
                session_id integer NOT NULL,
                shower varchar(6) NULL,
                "start" timestamp NOT NULL,
                "end" timestamp NOT NULL,
                user_id integer NULL,
                t_eff real NOT NULL,
                f real NOT NULL,
                lm real NOT NULL,
                method text NOT NULL,
                ra real,
                "dec" real,
                "number" integer NOT NULL,
                CONSTRAINT imported_rate_pkey PRIMARY KEY (id)
            )
        '''))

        super()._parse_csv_files(cur, files_list)

        cur.execute(db_conn.convert_stmt('''
            CREATE INDEX imported_rate_order_key ON
                imported_rate(
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
                rate_id = self._parse_rate_id(row['rate id'])
                session_id = self._parse_session_id(row['obs session id'], rate_id)
                shower = self._parse_shower(row['shower'])
                user_id = self._parse_observer_id(row['user id'], 'user id', rate_id)
                period_start = self._parse_date_time(row['start date'], 'start date', rate_id)
                period_end = self._parse_date_time(row['end date'], 'end date', rate_id)
                period_start, period_end = self._check_period(
                    period_start,
                    period_end,
                    timedelta(0, 3600 * 12),
                    rate_id
                )
                t_eff = self._parse_t_eff(row['teff'], rate_id)
                f = self._parse_f(row['f'], rate_id)
                freq = self._parse_freq(row['number'], rate_id)
                lm = self._parse_lm(row['lm'], rate_id)
                ra = self._parse_ra(row['ra'], rate_id)
                dec = self._parse_dec(row['decl'], rate_id)

                if (ra is None) ^ (dec is None):
                    self.logger.warning(
                        (
                            '%s: ra and dec must be set or both must be undefined.' + 
                            ' It is assumed that both values has not been set.'
                        ) % rate_id
                    )
                    ra = None
                    dec = None

            except ImportException as err:
                self._log_error(str(err))
                continue

            record = {
                'id': rate_id,
                'user_id': user_id,
                'session_id': session_id,
                'start': period_start,
                'end': period_end,
                't_eff': t_eff,
                'f': f,
                'lm': lm,
                'shower': shower,
                'method': row['method'],
                'number': freq,
                'ra': ra,
                'dec': dec,
            }
            cur.execute(self.insert_stmt, record)
            self.counter_write += 1

    @staticmethod
    def _parse_rate_id(rec):
        rate_id = rec.strip()
        if '' == rate_id:
            raise ImportException("Observation found without a rate id.")

        try:
            rate_id = int(rate_id)
        except ValueError:
            raise ImportException("%s: invalid rate id." % rate_id)
        if rate_id < 1:
            raise ImportException("%s: rate id must be greater than 0." % rate_id)

        return rate_id

    @staticmethod
    def _parse_t_eff(rec, obs_id):
        t_eff = rec.strip()
        if '' == t_eff:
            raise ImportException("%s: t_eff must be set." % obs_id)

        try:
            t_eff = float(t_eff)
        except ValueError:
            raise ImportException("%s: invalid t_eff. The value is %s." % (obs_id, t_eff))

        if 0.0 == t_eff:
            raise ImportException("%s: t_eff is 0." % obs_id)

        if t_eff < 0.0 or t_eff > 10:
            raise ImportException("%s: t_eff must be between 0 and 10 instead of %s." % (obs_id, t_eff))

        return t_eff

    @staticmethod
    def _parse_f(rec, obs_id):
        f = rec.strip()
        if '' == f:
            raise ImportException("%s: f must be set." % obs_id)

        try:
            f = float(f)
        except ValueError:
            raise ImportException("%s: invalid f. The value is %s." % (obs_id, f))

        if f < 1.0:
            raise ImportException("%s: f must be greater than 1 instead of %s." % (obs_id, f))

        return f

    @staticmethod
    def _parse_freq(rec, rate_id):
        value = rec.strip()

        try:
            value = int(value)
        except ValueError:
            raise ImportException("%s: %s is an invalid count of meteors." % (rate_id, value))

        if value < 0:
            raise ImportException(
                "%s: count of meteors must be greater than 0 instead of %s." %
                (rate_id, value)
            )

        return value

    @staticmethod
    def _parse_lm(rec, obs_id):
        lm = rec.strip()
        if '' == lm:
            raise ImportException("%s: limiting magnitude must be set." % obs_id)

        try:
            lm = float(lm)
        except ValueError:
            raise ImportException("%s: invalid limiting magnitude. The value is %s." % (obs_id, lm))

        if lm < 0.0 or lm > 8:
            raise ImportException("%s: lm must be between 0 and 8 instead of %s." % (obs_id, lm))

        return lm


def usage():
    print('''Imports rate observations.
Syntax: import_rates <options> files ...
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
                format='%(asctime)s import_rates[%(levelname)s] %(message)s',
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
    imp = RateImport(db_conn, logger)
    imp.run(args)
    db_conn.close()

    if imp.has_errors:
        print('Errors occurred when importing magnitude observations.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
