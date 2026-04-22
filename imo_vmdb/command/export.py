import csv
import os
import sys
from optparse import OptionParser
from pathlib import Path

from imo_vmdb.command import config_factory
from imo_vmdb.db import DBAdapter, DBException

_DATA_DIR = Path(os.path.dirname(os.path.realpath(__file__))).parent / 'data'

REIMPORT_TABLES = {'shower', 'radiant'}

STATIC_FILES = {
    'shower':  'showers.csv',
    'radiant': 'radiants.csv',
}

DB_TABLES = {
    'shower':           'shower',
    'radiant':          'radiant',
    'session':          'obs_session',
    'rate':             'rate',
    'magnitude':        'magnitude',
    'magnitude_detail': 'magnitude_detail',
    'rate_magnitude':   'rate_magnitude',
}

ALL_TABLES = list(DB_TABLES)


def main(command_args):
    parser = OptionParser(
        usage='export <table> [options]\n\nTables: ' + ', '.join(ALL_TABLES)
    )
    parser.add_option('-c', action='store', dest='config_file', help='path to config file')
    parser.add_option('-o', action='store', dest='output_file', metavar='FILE',
                      help='output file (default: stdout)')
    parser.add_option('--reimport', action='store_true', dest='reimport', default=False,
                      help='export in original import format (shower and radiant only)')
    options, args = parser.parse_args(command_args)

    if not args:
        parser.print_help()
        sys.exit(1)

    table = args[0]
    if table not in ALL_TABLES:
        print(f'Unknown table: {table!r}. Valid tables: {", ".join(ALL_TABLES)}', file=sys.stderr)
        sys.exit(1)

    out = open(options.output_file, 'w', newline='', encoding='utf-8') \
        if options.output_file else sys.stdout

    try:
        if table in REIMPORT_TABLES and options.reimport:
            _export_static(table, out)
        else:
            _export_db(table, options, parser, out)
    finally:
        if options.output_file:
            out.close()


def _export_static(table, out):
    src = _DATA_DIR / STATIC_FILES[table]
    with open(src, 'r', encoding='utf-8-sig') as f:
        out.write(f.read())


def _export_db(table, options, parser, out):
    try:
        config = config_factory(options, parser)
    except SystemExit:
        raise

    try:
        db_conn = DBAdapter(dict(config['database']))
        cur = db_conn.cursor()
        cur.execute(f'SELECT * FROM {DB_TABLES[table]}')
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        db_conn.close()
    except DBException as e:
        print(f'Database error: {e}', file=sys.stderr)
        sys.exit(100)

    writer = csv.writer(out, delimiter=';')
    writer.writerow(cols)
    writer.writerows(rows)
