import csv
import getopt
import json
import sys
import warnings
from vmdb.utils import DBAdapter, custom_formatwarning


def import_sessions(db_conn, files_list):

    cur = db_conn.cursor()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS obs_session'))

    cur.execute(db_conn.convert_stmt('''
        CREATE TABLE obs_session
        (
            id integer PRIMARY KEY,
            observer_id integer NULL,
            longitude real NOT NULL,
            latitude real NOT NULL,
            elevation real NOT NULL
        );
    '''))
    insert_stmt = db_conn.convert_stmt('''
        INSERT INTO obs_session (
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

    for session_path in files_list:

        with open(session_path, mode='r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            is_head = True
            for row in csv_reader:
                if is_head:
                    is_head = False
                    column_names = [r.lower() for r in row]
                    continue

                row = dict(zip(column_names, row))
                if '' == row['session id']:
                    warnings.warn("Session found without a session id. Discarded.")
                    continue

                session_id = row['session id']
                observer_id = row['observer id']
                if '' == observer_id:
                    warnings.warn("Session %s has no observer id. Ignored." % (session_id,))
                    observer_id = None

                if '' == row['latitude']:
                    warnings.warn("Session found without a site latitude. Discarded.")
                    continue

                lat = float(row['latitude'])
                if lat < -90 or lat > 90:
                    warnings.warn("Session %s has not a valid site latitude. Discarded." % (session_id,))
                    continue

                if '' == row['longitude']:
                    warnings.warn("Session found without a site longitude. Discarded.")
                    continue

                long = float(row['longitude'])
                if long < -180 or long > 180:
                    warnings.warn("Session %s has not a valid site longitude. Discarded." % (session_id,))
                    continue

                elevation = float(row['elevation'])
                record = {
                    'id': int(session_id),
                    'observer_id': int(observer_id) if observer_id is not None else None,
                    'latitude': lat,
                    'longitude': long,
                    'elevation': elevation
                }
                cur.execute(insert_stmt, record)
    cur.close()


def usage():
    print('''Imports observation sessions.
Syntax: import_sessions <options> files ...
    options
        -c, --config ... path to config file
        -h, --help   ... prints this help''')


def main(command_args):

    config = None

    try:
        opts, args = getopt.getopt(command_args, "hc:", ['help', 'config'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) < 1:
        usage()
        sys.exit(1)

    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--config"):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    warnings.formatwarning = custom_formatwarning
    warnings.simplefilter(config['warnings'] if 'warnings' in config else 'ignore')
    db_conn = DBAdapter(config['database'])
    import_sessions(db_conn, args)
    db_conn.commit()
    db_conn.close()
