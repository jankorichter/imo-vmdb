import csv
import getopt
import importlib
import json
import sys
from datetime import datetime


def import_magn(files_list, cur):
    cur.execute('DROP TABLE IF EXISTS imported_magn')
    cur.execute('''
        CREATE TABLE imported_magn
        (
            id integer NOT NULL,
            session_id integer NOT NULL,
            shower text NULL,
            "start" timestamp NOT NULL,
            "end" timestamp NOT NULL,
            user_id integer NOT NULL,
            magn text NOT NULL,
            CONSTRAINT imported_magn_pkey PRIMARY KEY (id)
        )
    ''')
    insert_stmt = '''
        INSERT INTO imported_magn (
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
            %("start")s,
            %("end")s,
            %(user_id)s,
            %(magn)s
        )
    '''

    for magn_path in files_list:

        with open(magn_path, mode='r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            is_head = True

            for row in csv_reader:
                if is_head:
                    is_head = False
                    column_names = [r.lower() for r in row]
                    continue

                row = dict(zip(column_names, row))
                if '' == row['magnitude id']:
                    continue

                period_start = datetime.strptime(row['start date'], '%Y-%m-%d %H:%M:%S')
                period_end = datetime.strptime(row['end date'], '%Y-%m-%d %H:%M:%S')

                if period_end <= period_start:
                    continue

                magn = {}
                for column in range(1, 7):
                    m = float(row['mag n' + str(column)])
                    if m > 0.0:
                        magn[str(-column)] = m

                for column in range(0, 8):
                    m = float(row['mag ' + str(column)])
                    if m > 0.0:
                        magn[str(column)] = m

                magn = json.dumps(magn)

                shower = row['shower'].strip()
                if '' == shower or 'SPO' == shower.upper():
                    shower = None

                record = {
                    'id': int(row['magnitude id']),
                    'session_id': int(row['obs session id']),
                    'shower': shower,
                    '"start"': row['start date'],
                    '"end"': row['end date'],
                    'user_id': int(row['user id']),
                    'magn': magn
                }
                cur.execute(insert_stmt, record)


def usage():
    print('''Imports VMDB magnitudes.
Syntax: import_magnitudes.py <options> files ...
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
    import_magn(args, cur)
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
