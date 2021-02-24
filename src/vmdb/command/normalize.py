import getopt
import json
import multiprocessing
import sys
import warnings
from vmdb.model.radiant import Storage as RadiantStorage
from vmdb.model.shower import Storage as ShowerStorage
from vmdb.model.solarlong import Solarlong
from vmdb.normalizer.db import create_tables, create_rate_magn
from vmdb.normalizer.magnitude import Normalizer as MagnitudeNormalizer
from vmdb.normalizer.rate import Normalizer as RateNormalizer
from vmdb.utils import DBAdapter, custom_formatwarning


class Normalizer(object):

    def __init__(self, db_conn, drop_tables, process_count, mod):
        self._drop_tables = drop_tables
        self._db_conn = db_conn
        self._process_count = process_count
        self._mod = mod

    def run(self):
        solarlongs = Solarlong(self._db_conn)
        radiant_storage = RadiantStorage(self._db_conn)
        radiants = radiant_storage.load()
        shower_storage = ShowerStorage(self._db_conn)
        showers = shower_storage.load(radiants)
        RateNormalizer(self._db_conn, solarlongs, showers)(self._drop_tables, self._process_count, self._mod)
        MagnitudeNormalizer(self._db_conn, solarlongs)(self._drop_tables, self._process_count, self._mod)


def process_init(config):
    warnings.formatwarning = custom_formatwarning
    warnings.simplefilter(config['warnings'] if 'warnings' in config else 'ignore')


def process(config, drop_tables, mod):
    process_init(config)
    process_count = int(config['process_count'] if 'process_count' in config else 1)
    db_conn = DBAdapter(config['database'])
    obj = Normalizer(db_conn, drop_tables, process_count, mod)
    obj.run()
    db_conn.commit()
    db_conn.close()


def usage():
    print('''Normalize and analyze meteor observations.
Syntax: normalize <options>
    -c, --config ... path to config file
    -d, --delete ... delete all data
    -h, --help   ... prints this help''')


def main(command_args):
    config = None

    try:
        opts, args = getopt.getopt(command_args, "hdc:", ['help', 'delete', 'config'])
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
    db_conn = DBAdapter(config['database'])
    create_tables(db_conn, drop_tables)
    db_conn.commit()

    process_count = int(config['process_count'] if 'process_count' in config else 1)
    if process_count > 1:
        processes = []
        ctx = multiprocessing.get_context('spawn')
        for i in range(process_count):
            p = ctx.Process(target=process, args=(config, drop_tables, i,))
            processes.append(p)
            p.start()

        for p in processes:
            p.join()
    else:
        obj = Normalizer(db_conn, drop_tables, 1, 0)
        obj.run()

    create_rate_magn(db_conn)
    db_conn.commit()
    db_conn.close()
