import csv
import getopt
import json
import logging
import sys
import warnings
from vmdb.model import DBAdapter
from vmdb.command import CsvImport, ImportException


class SessionImport(CsvImport):

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        self.required_columns = {
            'session id',
            'observer id',
            'latitude',
            'longitude',
            'elevation'
        }
        self.insert_stmt = db_conn.convert_stmt('''
            INSERT INTO imported_session (
                id,
                observer_id,
                latitude,
                longitude,
                elevation
            ) VALUES (
                %(id)s,
                %(observer_id)s,
                %(latitude)s,
                %(longitude)s,
                %(elevation)s
            )
        ''')

    def run(self, files_list):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_session'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_session
            (
                id integer PRIMARY KEY,
                observer_id integer NULL,
                longitude real NOT NULL,
                latitude real NOT NULL,
                elevation real NOT NULL
            );
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
                session_id = self._parse_session_id(row['session id'])
                observer_id = self._parse_observer_id(row['observer id'], 'observer id', session_id)
                lat = self._parse_latitude(row['latitude'], session_id)
                long = self._parse_longitude(row['longitude'], session_id)
                elevation = self._parse_elevation(row['longitude'], session_id)
            except ImportException as err:
                self._log_error(str(err))
                continue

            record = {
                'id': session_id,
                'observer_id': observer_id,
                'latitude': lat,
                'longitude': long,
                'elevation': elevation
            }
            cur.execute(self.insert_stmt, record)
            self.counter_write += 1

    @staticmethod
    def _parse_session_id(rec):
        session_id = rec.strip()
        if '' == session_id:
            raise ImportException("Session found without a session id.")

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException("%s: invalid session id." % session_id)
        if session_id < 1:
            raise ImportException("%s: session id must be greater than 0." % session_id)

        return session_id

    @staticmethod
    def _parse_latitude(rec, session_id):
        lat = rec.strip()
        if '' == lat:
            raise ImportException("%s: latitude must not be empty." % session_id)

        try:
            lat = float(lat)
        except ValueError:
            raise ImportException("%s: invalid latitude value. The value is %s." % (session_id, lat))

        if lat < -90 or lat > 90:
            raise ImportException("%s: latitude must be between -90 and 90 instead of %s." % (session_id, lat))

        return lat

    @staticmethod
    def _parse_longitude(rec, session_id):
        long = rec.strip()
        if '' == long:
            raise ImportException("%s: longitude must not be empty." % session_id)

        try:
            long = float(long)
        except ValueError:
            raise ImportException("%s: invalid longitude value. The value is %s." % (session_id, long))

        if long < -180 or long > 180:
            raise ImportException("%s: longitude must be between -180 and 180 instead of %s." % (session_id, long))

        return long

    @staticmethod
    def _parse_elevation(rec, session_id):
        elevation = rec.strip()
        if '' == elevation:
            raise ImportException("%s: elevation must not be empty." % session_id)

        try:
            elevation = float(elevation)
        except ValueError:
            raise ImportException("%s: invalid elevation value. The value is %s." % (session_id, elevation))

        return elevation


def usage():
    print('''Imports observation sessions.
Syntax: import_sessions <options> files ...
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
                format='%(asctime)s import_sessions[%(levelname)s] %(message)s',
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
    imp = SessionImport(db_conn, logger)
    imp.run(args)
    db_conn.close()

    if imp.has_errors:
        print('Errors occurred when importing sessions.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
