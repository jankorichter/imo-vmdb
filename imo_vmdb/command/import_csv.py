import sys
import imo_vmdb
from optparse import OptionParser
from imo_vmdb.command import config_factory, LoggerFactory
from imo_vmdb.db import DBAdapter, DBException


def main(command_args):
    parser = OptionParser(usage='import_csv [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    parser.add_option('-d', action='store_true', dest='delete', default=False,
                      help='deletes previously imported data')
    parser.add_option('-p', action='store_true', dest='permissive', default=False,
                      help='does not apply stringent tests')
    parser.add_option('-r', action='store_true', dest='repair', default=False,
                      help='an attempt is made to correct errors')
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)
    logger = logger_factory.get_logger('import_csv')

    kwargs = {
        'do_delete': options.delete,
        'is_permissive': options.permissive,
        'try_repair': options.repair
    }

    try:
        db_conn = DBAdapter(config['database'])
        csv_import = imo_vmdb.CSVImporter(db_conn, logger, **kwargs)
        csv_import.run(args)
        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(100)

    if csv_import.has_errors:
        print('Errors or warnings occurred when importing data.', file=sys.stderr)
        if logger_factory.log_file is not None:
            print('See log file %s for more information.' % logger_factory.log_file, file=sys.stderr)
        sys.exit(4)

    sys.exit(0)
