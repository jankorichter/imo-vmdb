import getopt
import json
import logging
import os
import sys
from pathlib import Path

from vmdb2sql.command.import_csv import CSVImport
from vmdb2sql.db import create_tables, DBAdapter, DBException


def usage():
    print('''Initializes the database.
Syntax: initdb <options>
    -c, --config ... path to config file
    -l, --log    ... path to log file
    -h, --help   ... prints this help''')


def main(command_args):

    config = None

    try:
        opts, args = getopt.getopt(
            command_args,
            'hc:l:',
            ['help', 'config', 'log']
        )
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 0:
        usage()
        sys.exit(1)

    log_file = None
    for o, a in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit()
        elif o in ('-c', '--config'):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        elif o in ('-l', '--log'):
            log_file = a
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    log_handler = None
    if log_file is not None:
        log_handler = logging.FileHandler(log_file, 'a')
        fmt = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s', None, '%')
        log_handler.setFormatter(fmt)

    logger = logging.getLogger('initdb')
    logger.disabled = True
    logger.setLevel(logging.INFO)
    if log_handler is not None:
        logger.addHandler(log_handler)
        logger.disabled = False

    my_dir = Path(os.path.dirname(os.path.realpath(__file__)))
    shower_file = str(my_dir.parent / 'data' / 'showers.csv')
    radiants_file = str(my_dir.parent / 'data' / 'radiants.csv')

    try:
        db_conn = DBAdapter(config['database'])
        logger.info('Starting initialization of the database.')
        create_tables(db_conn)
        logger.info('Database initialized.')
        csv_import = CSVImport(db_conn, log_handler, do_delete=True)
        csv_import.run((shower_file, radiants_file))
        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    if csv_import.has_errors:
        print('Errors or warnings occurred when importing data.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
