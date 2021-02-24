import csv
import getopt
import json
import sys
import warnings
from vmdb.utils import DBAdapter


def create_date(date_str):
    undef = [None, None]
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

    if '' == date_str:
        return undef

    value = date_str.split()
    if len(value) != 2:
        return undef

    month = month_names[value[0]]
    if month is None:
        return undef

    day = int(value[1])
    if day < 1 or day > 31:
        return undef

    if 31 == day and month in [4, 6, 9, 11]:
        return undef

    if 2 == month and day in [29, 30]:
        return undef

    return [month, day]


def import_showers(db_conn, shower_path):
        
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
    insert_stmt = db_conn.convert_stmt('''
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

    with open(shower_path, mode='r', encoding='utf-8-sig') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=';')
        is_head = True

        for row in csv_reader:
            if is_head:
                is_head = False
                column_names = [r.lower() for r in row]
                continue

            row = dict(zip(column_names, row))
            ra = row['ra'].strip()
            dec = row['de'].strip()
            if '' == ra or '' == dec:
                ra = None
                dec = None
            else:
                ra = float(ra)
                dec = float(dec)

            v = row['v'].strip()
            r = row['r'].strip()
            zhr = row['zhr'].strip()
            peak = create_date(row['peak'].strip())
            period_start = create_date(row['start'].strip())
            period_end = create_date(row['end'].strip())
            record = {
                'id': int(row['id'].strip()),
                'iau_code': row['iau_code'].strip(),
                'name': row['name'].strip(),
                'start_month': period_start[0],
                'start_day': period_start[1],
                'end_month': period_end[0],
                'end_day': period_end[1],
                'peak_month': peak[0],
                'peak_day': peak[1],
                'ra': ra,
                'dec': dec,
                'v': float(v) if '' != v else None,
                'r': float(r) if '' != r else None,
                'zhr': zhr if '' != zhr else None,
            }

            cur.execute(insert_stmt, record)

    cur.close()


def usage():
    print('''Imports meteor showers.
Syntax: import_showers <options> showers.csv
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
    import_showers(db_conn, args[0])
    db_conn.commit()
    db_conn.close()
