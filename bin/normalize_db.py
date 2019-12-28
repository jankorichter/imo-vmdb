import getopt
import json
import multiprocessing
import sys
from vmdb.model.radiant import Storage as RadiantStorage
from vmdb.model.shower import Storage as ShowerStorage
from vmdb.model.solarlong import Solarlong
from vmdb.normalizer.rate import Rate
from vmdb.normalizer.magnitude import Magnitude
from vmdb.utils import connection_decorator


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
        Rate(conn, solarlongs, showers)(self._drop_tables, self._process_count, self._mod)
        Magnitude(conn, solarlongs)(self._drop_tables, self._process_count, self._mod)


@connection_decorator
def create_tables(drop_tables, conn):
    cur = conn.cursor()

    if drop_tables:
        cur.execute('DROP TABLE IF EXISTS rate CASCADE')
        cur.execute('DROP TABLE IF EXISTS magnitude CASCADE')
        cur.execute('DROP TABLE IF EXISTS magnitude_detail CASCADE')
        cur.execute('DROP TABLE IF EXISTS rate_magnitude CASCADE')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS rate (
            id integer NOT NULL,
            shower char(5) NULL,
            period_start timestamp NOT NULL,
            period_end timestamp NOT NULL,
            sl_start double precision NOT NULL,
            sl_end double precision NOT NULL,
            session_id integer NOT NULL,
            observer_id integer NOT NULL,
            freq integer NOT NULL,
            lim_mag real NOT NULL,
            t_eff real NOT NULL,
            f real NOT NULL,
            t_zenith double precision NULL,
            rad_alt double precision NULL,
            CONSTRAINT rate_pkey PRIMARY KEY (id)
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS magnitude (
            id integer NOT NULL,
            shower char(5) NULL,
            period_start timestamp NOT NULL,
            period_end timestamp NOT NULL,
            sl_start double precision NOT NULL,
            sl_end double precision NOT NULL,
            session_id integer NOT NULL,
            observer_id integer NOT NULL,
            freq integer NOT NULL,
            mean double precision NOT NULL,
            lim_mag real NULL,
            CONSTRAINT magnitude_pkey PRIMARY KEY (id)
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS magnitude_detail (
            id integer NOT NULL,
            magn integer NOT NULL,
            freq real NOT NULL,
            CONSTRAINT magnitude_detail_pkey PRIMARY KEY (id, magn),
            CONSTRAINT magnitude_detail_fk FOREIGN KEY (id)
                REFERENCES magnitude(id) MATCH SIMPLE
                ON UPDATE CASCADE
                ON DELETE CASCADE
        )''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rate_magnitude (
            rate_id integer NOT NULL,
            magn_id integer NOT NULL,
            "equals" boolean NOT NULL,
            CONSTRAINT rate_magnitude_pkey PRIMARY KEY (rate_id),
            CONSTRAINT rate_magnitude_rate_fk FOREIGN KEY (rate_id)
                REFERENCES rate (id) MATCH SIMPLE
                ON UPDATE CASCADE
                ON DELETE CASCADE,
            CONSTRAINT rate_magnitude_magn_fk FOREIGN KEY (magn_id)
                REFERENCES magnitude(id) MATCH SIMPLE
                ON UPDATE CASCADE
                ON DELETE CASCADE

        )''')

    if drop_tables:
        cur.execute('CREATE INDEX fki_rate_magnitude_magn_fk ON rate_magnitude(magn_id)')

    cur.close()


@connection_decorator
def create_rate_magn(conn):
    cur = conn.cursor()
    cur.execute('TRUNCATE rate_magnitude CASCADE')

    # find magnitude-rate-pairs containing each other
    cur.execute('''
            WITH selection AS (
                SELECT
                    r.id as rate_id,
                    m.id as magn_id,
                    r.period_start as rate_period_start,
                    r.period_end as rate_period_end,
                    m.period_start as magn_period_start,
                    m.period_end as magn_period_end,
                    r.freq as rate_n,
                    m.freq as magn_n
                FROM rate as r
                INNER JOIN magnitude as m
                    ON
                       r.session_id = m.session_id AND
                       r.observer_id = m.observer_id AND
                       (
                           r.shower = m.shower OR
                           (r.shower IS NULL AND m.shower IS NULL)
                       )
            ),
            rate_magnitude_rel AS (
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    true as "equals"
                FROM selection
                WHERE
                   tsrange(rate_period_start, rate_period_end, '[)') = tsrange(magn_period_start, magn_period_end, '[)')
                UNION
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    false as "equals"
                FROM selection
                WHERE
                    NOT tsrange(rate_period_start, rate_period_end, '[)') @> tsrange(magn_period_start, magn_period_end, '[)') AND
                    tsrange(rate_period_start, rate_period_end, '[)') <@ tsrange(magn_period_start, magn_period_end, '[)')
            ),
            aggregates AS (
                SELECT
                    rate_id,
                    magn_id,
                    sum(rate_n) OVER (PARTITION BY magn_id) as rate_n,
                    magn_n,
                    "equals",
                    count(magn_id) OVER (PARTITION BY rate_id) as magn_id_count
                FROM rate_magnitude_rel
            ),
            unique_rate_ids AS (
                SELECT
                    rate_id,
                    magn_id,
                    "equals"
                FROM aggregates
                WHERE
                    magn_id_count = 1 AND
                    rate_n = magn_n
            )

            INSERT INTO rate_magnitude (rate_id, magn_id, "equals")
            SELECT rate_id, magn_id, "equals" FROM unique_rate_ids
    ''')

    # set limiting mggnitude
    cur.execute('UPDATE magnitude SET lim_mag = NULL')
    cur.execute('''
        UPDATE magnitude m
        SET lim_mag = round(s.lim_mag*100)/100.0
        FROM (
            SELECT rm.magn_id, sum(r.t_eff*r.lim_mag)/sum(r.t_eff) as lim_mag
            FROM rate r
            INNER JOIN rate_magnitude rm ON rm.rate_id = r.id
            GROUP BY rm.magn_id
        ) s
        WHERE s.magn_id = m.id
    ''')

    cur.close()


def process(config, drop_tables, mod):
    sys.modules['vmdb.utils'].config = config
    obj = Normalizer(drop_tables, int(config['process_count']), mod)
    obj.run()


def usage():
    print('''Normalize the data using the imported VMDB data.
Syntax: normalize.py <options>
    -c, --config ... path to config file
    -d, --delete ... delete all data
    -h, --help   ... prints this help''')


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

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

    sys.modules['vmdb.utils'].config = config
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


if __name__ == "__main__":
    main()
