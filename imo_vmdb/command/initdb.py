import os
import sys
from optparse import OptionParser
from pathlib import Path
from imo_vmdb.command import config_factory, LoggerFactory
from imo_vmdb.command.import_csv import CSVImport
from imo_vmdb.db import create_tables, DBAdapter, DBException


def main(command_args):
    parser = OptionParser(usage='initdb [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)
    logger = logger_factory.get_logger('initdb')

    my_dir = Path(os.path.dirname(os.path.realpath(__file__)))
    shower_file = str(my_dir.parent / 'data' / 'showers.csv')
    radiants_file = str(my_dir.parent / 'data' / 'radiants.csv')

    try:
        db_conn = DBAdapter(config['database'])
        logger.info('Starting initialization of the database.')
        create_tables(db_conn)
        logger.info('Database initialized.')
        csv_import = CSVImport(db_conn, logger_factory, do_delete=True)
        csv_import.run((shower_file, radiants_file))
        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    if csv_import.has_errors:
        print('Errors or warnings occurred when importing data.', file=sys.stderr)
        if logger_factory.log_file is not None:
            print('See log file %s for more information.' % logger_factory.log_file, file=sys.stderr)
        sys.exit(3)
