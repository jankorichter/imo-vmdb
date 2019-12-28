from datetime import datetime, timedelta
import getopt
import json
import sys
from vmdb.model.solarlong import Solarlong
from vmdb.utils import connection_decorator


@connection_decorator
def truncate_table(conn):
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS imported_solarlong (
            date DATE NOT NULL,
            sl double precision NOT NULL,
            CONSTRAINT imported_solarlong_pkey PRIMARY KEY (date)
    )''')
    cur.execute('TRUNCATE imported_solarlong')
    cur.close()


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


@connection_decorator
def import_solarlongs(start_date, end_date, conn):
    solarlong = Solarlong(conn)
    diff = timedelta(days=1)
    cur = conn.cursor()
    insert_stmt = '''
        INSERT INTO imported_solarlong (
            date,
            sl
        ) VALUES (
            %(date)s,
            %(sl)s
        )
    '''

    for time_list in date_generator(start_date, end_date, diff):
        sl_list = solarlong.calculate(time_list)

        for z in zip(time_list, sl_list):
            record = {
                'date': z[0].strftime("%Y-%m-%d"),
                'sl': z[1],
            }
            cur.execute(insert_stmt, record)

    cur.close()


def usage():
    print('''Generates solarlongs.
Syntax: import_solarlong.py <options>
    options
        -c, --config ... path to config file
        -s, --start  ... start date (YYYY-MM-DD)
        -e, --end    ... end date (YYYY-MM-DD)
        -h, --help   ... prints this help''')


def main():
    if len(sys.argv) < 6:
        usage()
        sys.exit(1)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hc:s:e:", ['help', 'config', 'start', 'end'])
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

    sys.modules['vmdb.utils'].config = config
    truncate_table()
    import_solarlongs(start_date, end_date)


if __name__ == "__main__":
    main()
