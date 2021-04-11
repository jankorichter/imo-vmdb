import configparser
import sys
from optparse import OptionParser
from imo_vmdb.db import DBAdapter, DBException


def main(command_args):
    parser = OptionParser(usage='cleanup [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    options, args = parser.parse_args(command_args)

    if options.config_file is None:
        parser.print_help()
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(options.config_file)

    try:
        db_conn = DBAdapter(config['database'])
        cur = db_conn.cursor()
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_magnitude'))
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_rate'))
        cur.execute(db_conn.convert_stmt('DELETE FROM imported_session'))
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    cur.close()
    db_conn.commit()
    db_conn.close()