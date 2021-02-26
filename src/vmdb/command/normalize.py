import getopt
import json
import logging
import sys
from vmdb.model.radiant import Storage as RadiantStorage
from vmdb.model.shower import Storage as ShowerStorage
from vmdb.model.solarlong import Solarlong
from vmdb.normalizer import create_tables, create_rate_magn
from vmdb.normalizer.magnitude import MagnitudeNormalizer
from vmdb.normalizer.rate import RateNormalizer
from vmdb.model import DBAdapter


def usage():
    print('''Normalize and analyze meteor observations.
Syntax: normalize <options>
    -c, --config ... path to config file
    -d, --delete ... delete all data
    -l, --log    ... path to log file
    -h, --help   ... prints this help''')


def main(command_args):
    config = None

    try:
        opts, args = getopt.getopt(command_args, "hdc:l:", ['help', 'delete', 'config', 'log'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 0:
        usage()
        sys.exit(1)

    logger = logging.getLogger()
    logger.disabled = True
    log_file = None

    drop_tables = False
    for o, a in opts:
        if o in ("-h", "--help"):
            usage()
            sys.exit()
        if o in ("-d", "--delete"):
            drop_tables = True
        elif o in ("-c", "--config"):
            with open(a) as json_file:
                config = json.load(json_file, encoding='utf-8-sig')
        elif o in ("-l", "--log"):
            log_file = a
            logging.basicConfig(
                filename=log_file,
                format='%(asctime)s [%(levelname)s] %(message)s',
                level=logging.INFO
            )
            logger.disabled = False
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    db_conn = DBAdapter(config['database'])
    create_tables(db_conn, drop_tables)
    db_conn.commit()

    solarlongs = Solarlong(db_conn)
    radiant_storage = RadiantStorage(db_conn)
    radiants = radiant_storage.load()
    shower_storage = ShowerStorage(db_conn)
    showers = shower_storage.load(radiants)
    rn = RateNormalizer(db_conn, logger, drop_tables, solarlongs, showers)
    logger.info("Start normalizing the rates.")
    rn.run()
    logger.info(
        "The normalisation of the rates has been completed. %s of %s records have been written." %
        (rn.counter_write, rn.counter_read)
    )
    mn = MagnitudeNormalizer(db_conn, logger, drop_tables, solarlongs)
    logger.info("Start normalizing the magnitudes.")
    mn.run()
    logger.info(
        "The normalisation of the magnitudes has been completed. %s of %s records have been written." %
        (rn.counter_write, rn.counter_read)
    )

    create_rate_magn(db_conn)
    db_conn.commit()
    db_conn.close()

    if rn.has_errors or mn.has_errors:
        print('Errors occurred when normalizing.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
