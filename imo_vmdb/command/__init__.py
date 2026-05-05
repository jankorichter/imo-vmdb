import configparser
import logging
import os
import sys
from configparser import RawConfigParser
from typing import Any


def config_factory(options: Any, parser: Any) -> RawConfigParser:
    """Build a :class:`~configparser.RawConfigParser` from a config file and/or environment variables.

    Resolution order:

    1. ``IMO_VMDB_CONFIG`` environment variable (overridden by the ``-c`` CLI flag).
    2. ``IMO_VMDB_<SECTION>_<KEY>`` environment variables fill gaps not already
       set by the file.

    Exits with code 1 if no ``[database]`` section or ``database`` key is present.

    :param options: Parsed CLI options object; must expose a ``config_file``
        attribute (``str`` or ``None``).
    :param parser: CLI parser used to print usage and exit on configuration errors.
    :return: Populated :class:`~configparser.RawConfigParser` instance.
    """
    config = configparser.ConfigParser()

    # Config file is read first — it takes precedence over environment variables
    config_file = os.environ.get("IMO_VMDB_CONFIG")
    if options.config_file is not None:
        config_file = str(options.config_file)
    if config_file is not None:
        config.read(config_file)

    # Generic fallback: IMO_VMDB_<SECTION>_<KEY> → [section] key
    prefix = "IMO_VMDB_"
    for name, value in os.environ.items():
        if not name.startswith(prefix) or name == "IMO_VMDB_CONFIG":
            continue
        rest = name[len(prefix) :]
        if "_" not in rest:
            continue
        section, key = rest.split("_", 1)
        section = section.lower()
        key = key.lower()
        if not config.has_option(section, key):
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key, value)

    if not config.has_section("database") or not config.get(
        "database", "database", fallback=None
    ):
        parser.print_help()
        sys.exit(1)

    return config


class LoggerFactory:
    """Creates and configures a :class:`logging.Logger` for a command.

    Log output goes to stdout (default) or to a file when ``[logging] file``
    is set in the configuration.

    :param config: Parsed configuration.
    """

    def __init__(self, config: RawConfigParser) -> None:
        self._log_level = config.get("logging", "level", fallback=logging.INFO)
        log_file = config.get("logging", "file", fallback=None)

        if log_file is None or log_file == "":
            self.log_file = None
            handler = logging.StreamHandler(sys.stdout)
        else:
            self.log_file = log_file
            handler = logging.FileHandler(log_file, "a")

        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s", None, "%"
            )
        )
        self._log_handler = handler

    def get_logger(self, name: str) -> logging.Logger:
        """Return a logger named *name* configured with this factory's handler and level.

        :param name: Logger name (typically the command name, e.g. ``'import_csv'``).
        :return: Configured :class:`logging.Logger` instance.
        """
        logger = logging.getLogger(name)
        logger.addHandler(self._log_handler)
        logger.setLevel(self._log_level)

        return logger
