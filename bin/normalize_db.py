import getopt
import json
import multiprocessing
import sys
import warnings
from vmdb.model.radiant import Storage as RadiantStorage
from vmdb.model.shower import Storage as ShowerStorage
from vmdb.model.solarlong import Solarlong
from vmdb.normalizer.db import create_tables, create_rate_magn, create_r_views
from vmdb.normalizer.rate import Normalizer as RateNormalizer
from vmdb.normalizer.magnitude import Normalizer as MagnitudeNormalizer
from vmdb.utils import connection_decorator, custom_formatwarning


class Normalizer(object):

    def __init__(self, drop_tables, process_count, mod):
        self._drop_tables = drop_tables
        self._process_count = process_count
        self._mod = mod

    @connection_decorator
    def run(self, conn):
        solarlongs = Solarlong(conn)
        radiant_storage = RadiantStorage(conn)
        radiants = radiant_storage.load()
        shower_storage = ShowerStorage(conn)
        showers = shower_storage.load(radiants)
        RateNormalizer(conn, solarlongs, showers)(self._drop_tables, self._process_count, self._mod)
        MagnitudeNormalizer(conn, solarlongs)(self._drop_tables, self._process_count, self._mod)


def process_init(config):
    warnings.formatwarning = custom_formatwarning
    warnings.simplefilter(config['warnings'] if 'warnings' in config else 'ignore')
    sys.modules['vmdb.utils'].config = config


def process(config, drop_tables, mod):
    process_init(config)
    process_count = int(config['process_count'])
    obj = Normalizer(drop_tables, process_count, mod)
    obj.run()


def usage():
    print('''Normalize the data using the imported VMDB data.
Syntax: normalize.py <options>
    -c, --config ... path to config file
    -d, --delete ... delete all data
    -h, --help   ... prints this help''')


def main():
    config = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hdc:", ['help', 'delete', 'config'])
    except getopt.GetoptError as err:
        print(str(err), file=sys.stderr)
        usage()
        sys.exit(2)

    if len(args) != 0:
        usage()
        sys.exit(1)

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
        else:
            print('invalid option ' + o, file=sys.stderr)
            usage()
            sys.exit(2)

    if config is None:
        usage()
        sys.exit(1)

    process_init(config)
    create_tables(drop_tables)
    process_count = int(config['process_count'])
    processes = []
    ctx = multiprocessing.get_context('spawn')
    for i in range(process_count):
        p = ctx.Process(target=process, args=(config, drop_tables, i,))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    create_rate_magn()
    create_r_views()


if __name__ == "__main__":
    main()
