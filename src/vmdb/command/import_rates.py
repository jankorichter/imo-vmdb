import csv
import getopt
import json
import sys
import warnings
from datetime import datetime, timedelta
from vmdb.utils import DBAdapter, check_period, custom_formatwarning


def import_rate(db_conn, files_list):
    
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
            user_id integer NOT NULL,
            t_eff real NOT NULL,
            f real NOT NULL,
            lm real NOT NULL,
            method text NOT NULL,
            "number" integer NOT NULL,
            CONSTRAINT imported_rate_pkey PRIMARY KEY (id)
        )
    '''))
    insert_stmt = db_conn.convert_stmt('''
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

    for rate_path in files_list:

        with open(rate_path, mode='r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=';')
            is_head = True

            for row in csv_reader:
                if is_head:
                    is_head = False
                    column_names = [r.lower() for r in row]
                    continue

                row = dict(zip(column_names, row))
                if '' == row['obs session id']:
                    warnings.warn("Observation found without a obs session id. Discarded.")
                    continue

                if '' == row['rate id']:
                    warnings.warn("Observation found without a rate id. Discarded.")
                    continue

                if '' == row['user id']:
                    warnings.warn("Observation found without a user id. Discarded.")
                    continue

                rate_id = row['rate id']
                shower = row['shower'].strip()

                if '' == shower or 'SPO' == shower.upper():
                    shower = None

                period_start = datetime.strptime(row['start date'], '%Y-%m-%d %H:%M:%S')
                period_end = datetime.strptime(row['end date'], '%Y-%m-%d %H:%M:%S')
                period_start, period_end = check_period(rate_id, period_start, period_end, timedelta(0, 3600 * 12))
                if period_start is None or period_end is None:
                    continue

                t_eff = float(row['teff'])
                if t_eff <= 0.0:
                    warnings.warn(
                        "Observation %s has an invalid observation time %s. Discarded." % (rate_id, str(t_eff)))
                    continue

                f = float(row['f'])
                if f < 1.0:
                    warnings.warn("Observation %s has an invalid time correction %s. Discarded." % (rate_id, str(f)))
                    continue

                count = int(row['number'])
                if count < 0:
                    warnings.warn(
                        "Observation %s has an invalid count of %s meteors. Discarded." % (rate_id, str(count)))
                    continue

                record = {
                    'id': int(rate_id),
                    'user_id': int(row['user id']),
                    'session_id': int(row['obs session id']),
                    'start': row['start date'],
                    'end': row['end date'],
                    't_eff': t_eff,
                    'f': f,
                    'lm': float(row['lm']),
                    'shower': shower,
                    'method': row['method'],
                    'number': count,
                }
                cur.execute(insert_stmt, record)

    cur.execute(db_conn.convert_stmt('''
        CREATE INDEX imported_rate_order_key ON
            imported_rate(
                session_id,
                shower,
                "start",
                "end"
            )
    '''))
    cur.close()


def usage():
    print('''Imports rate observations.
Syntax: import_rates <options> files ...
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
    import_rate(db_conn, args)
    db_conn.commit()
    db_conn.close()
