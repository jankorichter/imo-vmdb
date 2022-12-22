import sys
from optparse import OptionParser
from imo_vmdb.command import config_factory, LoggerFactory
from imo_vmdb.db import DBAdapter, DBException
from imo_vmdb.model.radiant import Storage as RadiantStorage
from imo_vmdb.model.shower import Storage as ShowerStorage
from imo_vmdb.model.sky import Sky
from imo_vmdb.normalizer import create_rate_magn
from imo_vmdb.normalizer.magnitude import MagnitudeNormalizer
from imo_vmdb.normalizer.rate import RateNormalizer
from imo_vmdb.normalizer.session import SessionNormalizer


def main(command_args):
    parser = OptionParser(usage='normalize [options]')
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)
    logger = logger_factory.get_logger('normalize')

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
        logger.info('Normalisation completed.')
    except DBException as e:
        msg = 'A database error occured. %s' % str(e)
        print(msg, file=sys.stderr)
        sys.exit(3)

    if rn.has_errors or mn.has_errors:
        print('Errors occurred when normalizing.', file=sys.stderr)
        if logger_factory.log_file is not None:
            print('See log file %s for more information.' % logger_factory.log_file, file=sys.stderr)
        sys.exit(3)
