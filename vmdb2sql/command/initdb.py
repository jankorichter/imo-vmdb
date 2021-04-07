import json
import logging
import os
import sys
from optparse import OptionParser
from pathlib import Path
from vmdb2sql.command.import_csv import CSVImport
from vmdb2sql.db import create_tables, DBAdapter, DBException


def main(command_args):
    parser = OptionParser(usage='initdb [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    parser.add_option('-l', action='store', dest='log_file', help='path to log file')
    options, args = parser.parse_args(command_args)

    if options.config_file is None:
        parser.print_help()
        sys.exit(1)

    with open(options.config_file) as json_file:
        config = json.load(json_file, encoding='utf-8-sig')

    log_handler = None
    if options.log_file is not None:
        log_handler = logging.FileHandler(options.log_file, 'a')
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
        if options.log_file is not None:
            print('See log file %s for more information.' % options.log_file, file=sys.stderr)
        sys.exit(3)
