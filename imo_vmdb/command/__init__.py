import configparser
import logging
import os
import sys


def config_factory(options, parser):
    config = configparser.ConfigParser()

    # Config file is read first — it takes precedence over environment variables
    config_file = os.environ.get('IMO_VMDB_CONFIG')
    if options.config_file is not None:
        config_file = str(options.config_file)
    if config_file is not None:
        config.read(config_file)

    # Generic fallback: IMO_VMDB_<SECTION>_<KEY> → [section] key
    prefix = 'IMO_VMDB_'
    for name, value in os.environ.items():
        if not name.startswith(prefix) or name == 'IMO_VMDB_CONFIG':
            continue
        rest = name[len(prefix):]
        if '_' not in rest:
            continue
        section, key = rest.split('_', 1)
        section = section.lower()
        key = key.lower()
        if not config.has_option(section, key):
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key, value)

    if not config.has_section('database') or not config.get('database', 'database', fallback=None):
        parser.print_help()
        sys.exit(1)

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
