import getopt
import json
import logging
import sys
from vmdb2sql.db import DBAdapter, DBException
from vmdb2sql.model.radiant import Storage as RadiantStorage
from vmdb2sql.model.shower import Storage as ShowerStorage
from vmdb2sql.model.sky import Sky
from vmdb2sql.normalizer import create_rate_magn
from vmdb2sql.normalizer.magnitude import MagnitudeNormalizer
from vmdb2sql.normalizer.rate import RateNormalizer
from vmdb2sql.normalizer.session import SessionNormalizer


def usage():
    print('''Normalize and analyze meteor observations.
Syntax: normalize <options>
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

    logger = logging.getLogger()
    logger.disabled = True
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
            logging.basicConfig(
                filename=log_file,
                format='%(asctime)s %(levelname)s [normalizer] %(message)s',
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

    try:
        db_conn = DBAdapter(config['database'])
        logger.info('Starting normalization of the sessions.')
        sn = SessionNormalizer(db_conn, logger)
        sn.run()
        logger.info(
            'The normalisation of the sessions has been completed. %s of %s records have been written.' %
            (sn.counter_write, sn.counter_read)
        )

        logger.info('Start of normalization the rates.')
        radiant_storage = RadiantStorage(db_conn)
        radiants = radiant_storage.load()
        shower_storage = ShowerStorage(db_conn)
        showers = shower_storage.load(radiants)
        sky = Sky()
        rn = RateNormalizer(db_conn, logger, sky, showers)
        rn.run()
        logger.info(
            'The normalisation of the rates has been completed. %s of %s records have been written.' %
            (rn.counter_write, rn.counter_read)
        )

        logger.info('Start of normalization the magnitudes.')
        mn = MagnitudeNormalizer(db_conn, logger, sky)
        mn.run()
        logger.info(
            'The normalisation of the magnitudes has been completed. %s of %s records have been written.' %
            (rn.counter_write, rn.counter_read)
        )

        logger.info('Start creating rate magnitude relationship.')
        create_rate_magn(db_conn)
        logger.info('The relationship between rate and magnitude was created.')

        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    if rn.has_errors or mn.has_errors:
        print('Errors occurred when normalizing.', file=sys.stderr)
        if not logger.disabled:
            print('See log file %s for more information.' % log_file, file=sys.stderr)
        sys.exit(3)
