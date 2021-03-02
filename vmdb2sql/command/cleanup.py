import getopt
import json
import sys
from vmdb2sql.db import DBAdapter, DBException


def usage():
    print('''Removes data that are no longer needed.
Syntax: cleanup <options>
        -c, --config ... path to config file
        -h, --help   ... prints this help''')


def main(command_args):

    config = None

    try:
        opts, args = getopt.getopt(
            command_args,
            'hc:', 
            ['help', 'config']
        )
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 0:
        usage()
        sys.exit(1)

    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()
        elif o in ('-c', '--config'):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    try:
        db_conn = DBAdapter(config['database'])
        cur = db_conn.cursor()
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_magnitude'))
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_rate'))
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_session'))

        if 'sqlite3' == db_conn.db_module:
            cur.execute('VACUUM')
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    cur.close()
    db_conn.commit()
    db_conn.close()