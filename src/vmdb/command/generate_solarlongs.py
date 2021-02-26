import getopt
import json
import sys
import warnings
from datetime import datetime, timedelta
from vmdb.model.solarlong import Solarlong
from vmdb.model import DBAdapter


def date_generator(start_date, end_date, diff):
    i = 0
    data = []
    t = start_date
    while t <= end_date:
        data.append(t)

        if i > 1000:
            yield data
            i = 0
            data = []

        i += 1
        t = t + diff

    if len(data) > 0:
        yield data


def import_solarlongs(db_conn, start_date, end_date):

    cur = db_conn.cursor()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS solarlong_lookup'))

    cur.execute(db_conn.convert_stmt('''
        CREATE TABLE solarlong_lookup (
            date DATE NOT NULL,
            sl double precision NOT NULL,
            CONSTRAINT solarlong_lookup_pkey PRIMARY KEY (date)
    )'''))

    solarlong = Solarlong(db_conn)
    diff = timedelta(days=1)
    insert_stmt = db_conn.convert_stmt('''
        INSERT INTO solarlong_lookup (
            date,
            sl
        ) VALUES (
            %(date)s,
            %(sl)s
        )
    ''')

    for time_list in date_generator(start_date, end_date, diff):
        sl_list = solarlong.calculate(time_list)

        for z in zip(time_list, sl_list):
            record = {
                'date': z[0].strftime("%Y-%m-%d"),
                'sl': float(z[1]),
            }
            cur.execute(insert_stmt, record)

    cur.close()


def usage():
    print('''Generates a solarlong lookup table.
Syntax: generate_solarlongs <options>
    options
        -c, --config ... path to config file
        -s, --start  ... start date (YYYY-MM-DD)
        -e, --end    ... end date (YYYY-MM-DD)
        -h, --help   ... prints this help''')


def main(command_args):
    if len(command_args) < 6:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(command_args, "hc:s:e:", ['help', 'config', 'start', 'end'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 0:
        usage()
        sys.exit(1)

    start_date = None
    end_date = None
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        elif o in ("-c", "--config"):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        elif o in ("-s", "--start"):
            start_date = datetime.strptime(a, '%Y-%m-%d')
        elif o in ("-e", "--end"):
            end_date = datetime.strptime(a, '%Y-%m-%d')
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    db_conn = DBAdapter(config['database'])
    import_solarlongs(db_conn, start_date, end_date)
    db_conn.commit()
    db_conn.close()
