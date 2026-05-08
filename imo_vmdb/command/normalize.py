import sys
from optparse import OptionParser

import imo_vmdb
from imo_vmdb import DBAdapter, DBException
from imo_vmdb.command import LoggerFactory, config_factory


def main(command_args: list[str]) -> None:
    """Parse arguments and run the normalisation command.

    :param command_args: CLI argument list (typically ``sys.argv[1:]``).
    """
    parser = OptionParser(usage="normalize [options]")
    parser.add_option(
        "-c", action="store", dest="config_file", help="path to config file"
    )
    options, args = parser.parse_args(command_args)
    config = config_factory(options, parser)
    logger_factory = LoggerFactory(config)
    logger = logger_factory.get_logger("normalize")

    try:
        db_conn = DBAdapter(config["database"])
        result = imo_vmdb.normalize(db_conn, logger)
        db_conn.commit()
        db_conn.close()
    except DBException as e:
        msg = "A database error occured. %s" % str(e)
        print(msg, file=sys.stderr)
        sys.exit(100)

    if result > 0:
        print("Errors occurred when normalizing.", file=sys.stderr)
        if logger_factory.log_file is not None:
            print(
                "See log file %s for more information." % logger_factory.log_file,
                file=sys.stderr,
            )

    sys.exit(result)
