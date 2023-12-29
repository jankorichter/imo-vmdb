import sys
import imo_vmdb
from optparse import OptionParser
from imo_vmdb.command import config_factory, LoggerFactory
from imo_vmdb.db import DBAdapter, DBException


def main(command_args):
    parser = OptionParser(usage='cleanup [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)
    logger = logger_factory.get_logger('cleanup')

    try:
        db_conn = DBAdapter(config['database'])
        result = imo_vmdb.cleanup(db_conn, logger)
        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(100)

    if result > 0:
        print('Errors or warnings occurred when cleaning up data.', file=sys.stderr)
        if logger_factory.log_file is not None:
            print('See log file %s for more information.' % logger_factory.log_file, file=sys.stderr)

    sys.exit(result)
