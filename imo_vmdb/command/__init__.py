import logging
import sys


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
