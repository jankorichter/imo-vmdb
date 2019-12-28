import csv
import getopt
import importlib
import json
import sys


def import_sessions(files_list, cur):
    cur.execute('DROP TABLE IF EXISTS imported_session')
    cur.execute('''
        CREATE TABLE imported_session
        (
            id integer PRIMARY KEY,
            observer_id integer NOT NULL,
            longitude real NOT NULL,
            latitude real NOT NULL,
            elevation real NOT NULL
        );
    ''')
    insert_stmt = '''
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
    '''

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
                if '' == row['session id'] or '' == row['observer id']:
                    continue

                lat = float(row['latitude'])
                if lat < -90 or lat > 90:
                    continue

                long = float(row['longitude'])
                if long < -180 or long > 180:
                    continue

                elevation = float(row['elevation'])
                record = {
                    'id': int(row['session id']),
                    'observer_id': int(row['observer id']),
                    'latitude': lat,
                    'longitude': long,
                    'elevation': elevation
                }
                cur.execute(insert_stmt, record)


def usage():
    print('''Imports VMDB sessions.
Syntax: import_sessions.py <options> files ...
    options
        -c, --config ... path to config file
        -h, --help   ... prints this help''')


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:", ['help', 'config'])
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

    db_config = config['database']
    db = importlib.import_module(db_config['module'])
    conn = db.connect(**db_config['connection'])
    cur = conn.cursor()
    import_sessions(args, cur)
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
