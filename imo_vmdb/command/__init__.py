import configparser
import logging
import os
import sys


def config_factory(options, parser):
    config = configparser.ConfigParser()
    config_file = os.environ['IMO_VMDB_CONFIG'] if 'IMO_VMDB_CONFIG' in os.environ else None

    if options.config_file is not None:
        config_file = str(options.config_file)

    if config_file is None:
        parser.print_help()
        sys.exit(1)

    config.read(config_file)
    return config


class LoggerFactory(object):

    def __init__(self, config):
        self._log_level = config.get('logging', 'level', fallback=logging.INFO)
        log_file = config.get('logging', 'file', fallback=None)

        if log_file is None or log_file == "":
            self.log_file = None
            handler = logging.StreamHandler(sys.stdout)
        else:
            self.log_file = log_file
            handler = logging.FileHandler(log_file, 'a')

        handler.setFormatter(
            logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s', None, '%')
        )
        self._log_handler = handler

    def get_logger(self, name):
        logger = logging.getLogger(name)
        logger.addHandler(self._log_handler)
        logger.setLevel(self._log_level)

        return logger
