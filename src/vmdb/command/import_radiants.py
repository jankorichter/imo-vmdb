import csv
import getopt
import json
import sys
import warnings
from vmdb.utils import DBAdapter


def import_radiants(db_conn, radiants_path):
    cur = db_conn.cursor()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_radiant'))

    cur.execute(db_conn.convert_stmt('''
        CREATE TABLE imported_radiant
        (
            shower char(3) NOT NULL,
            "month" integer NOT NULL,
            "day" integer NOT NULL,
            ra real NOT NULL,
            "dec" real NOT NULL,
            CONSTRAINT imported_radiant_pkey PRIMARY KEY (shower, "month", "day")
        )
    '''))
    insert_stmt = db_conn.convert_stmt('''
        INSERT INTO imported_radiant (
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

    with open(radiants_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=';')
        is_head = True

        for row in csv_reader:
            if is_head:
                is_head = False
                column_names = [r.lower() for r in row]
                continue

            row = dict(zip(column_names, row))
            shower = row['shower'].strip()
            ra = float(row['ra'])
            dec = float(row['dec'])
            day = int(row['day'])
            month = int(row['month'])

            if dec < -90 or dec > 90:
                raise AttributeError("dec must between -90 and 90")

            if ra < 0 or ra > 360:
                raise AttributeError("ra must between 0 and 360")

            if month < 1 or month > 12:
                raise AttributeError("month must between 1 and 12")

            if day < 1 or day > 31:
                raise AttributeError("day must between 1 and 31")

            if 31 == day and month in [4, 6, 9, 11]:
                raise AttributeError("day must be less than 31")

            if 2 == month and day in [29, 30]:
                raise AttributeError("day must be less than 29")

            record = {
                'shower': shower,
                'ra': ra,
                'dec': dec,
                'month': month,
                'day': day,
            }
            cur.execute(insert_stmt, record)

    cur.close()


def usage():
    print('''Imports radiant positions.
Syntax: import_radiants <options> radiants.csv
    options
        -c, --config ... path to config file
        -h, --help   ... prints this help''')


def main(command_args):

    if len(command_args) < 1:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(command_args, "hc:", ['help', 'config'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 1:
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

    db_conn = DBAdapter(config['database'])
    import_radiants(db_conn, args[0])
    db_conn.commit()
    db_conn.close()
