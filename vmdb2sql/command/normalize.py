import json
import logging
import sys
from optparse import OptionParser
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

    logger = logging.getLogger('normalize')
    logger.disabled = True
    logger.setLevel(logging.INFO)
    if log_handler is not None:
        logger.addHandler(log_handler)
        logger.disabled = False

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
        if options.log_file is not None:
            print('See log file %s for more information.' % options.log_file, file=sys.stderr)
        sys.exit(3)
