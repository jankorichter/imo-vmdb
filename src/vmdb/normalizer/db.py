import warnings
from vmdb.utils import connection_decorator


@connection_decorator
def create_tables(drop_tables, conn):
    cur = conn.cursor()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        if drop_tables:
            cur.execute('DROP TABLE IF EXISTS rate_magnitude CASCADE')
            cur.execute('DROP TABLE IF EXISTS magnitude_detail CASCADE')
            cur.execute('DROP TABLE IF EXISTS magnitude CASCADE')
            cur.execute('DROP TABLE IF EXISTS rate CASCADE')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS rate (
                id integer NOT NULL,
                shower varchar(6) NULL,
                period_start timestamp NOT NULL,
                period_end timestamp NOT NULL,
                sl_start double precision NOT NULL,
                sl_end double precision NOT NULL,
                session_id integer NOT NULL,
                observer_id integer NULL,
                freq integer NOT NULL,
                lim_mag real NOT NULL,
                t_eff real NOT NULL,
                f real NOT NULL,
                t_zenith double precision NULL,
                rad_alt double precision NULL,
                CONSTRAINT rate_pkey PRIMARY KEY (id)
            )''')

        if drop_tables:
            cur.execute('CREATE INDEX rate_period_shower_key ON rate(period_start, period_end, shower)')

        cur.execute('''
            CREATE TABLE IF NOT EXISTS magnitude (
                id integer NOT NULL,
                shower varchar(6) NULL,
                period_start timestamp NOT NULL,
                period_end timestamp NOT NULL,
                sl_start double precision NOT NULL,
                sl_end double precision NOT NULL,
                session_id integer NOT NULL,
                observer_id integer NULL,
                freq integer NOT NULL,
                mean double precision NOT NULL,
                lim_mag real NULL,
                CONSTRAINT magnitude_pkey PRIMARY KEY (id)
            )''')

        if drop_tables:
            cur.execute('CREATE INDEX magnitude_period_shower_key ON rate(period_start, period_end, shower)')

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

        if drop_tables:
            cur.execute('CREATE INDEX fki_magnitude_detail_fk ON magnitude_detail(id)')

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

        cur.execute('TRUNCATE rate_magnitude')

        if drop_tables:
            cur.execute('CREATE INDEX fki_rate_magnitude_magn_fk ON rate_magnitude(magn_id)')

    cur.close()


@connection_decorator
def create_rate_magn(conn):
    cur = conn.cursor()

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
               rate_period_start = magn_period_start AND
               rate_period_end = magn_period_end
            UNION
            SELECT
                rate_id,
                magn_id,
                rate_n,
                magn_n,
                false as "equals"
            FROM selection
            WHERE
                -- magnitude period contains rate period
                rate_period_start BETWEEN magn_period_start AND magn_period_end AND
                rate_period_end BETWEEN magn_period_start AND magn_period_end AND
                NOT (
                    -- rate period contains magnitude period
                    magn_period_start BETWEEN rate_period_start AND rate_period_end AND
                    magn_period_end BETWEEN rate_period_start AND rate_period_end
                )
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

        SELECT rate_id, magn_id, "equals" FROM unique_rate_ids
    ''')
    column_names = [desc[0] for desc in cur.description]
    insert_stmt = '''
        INSERT INTO rate_magnitude (
            rate_id,
            magn_id,
            "equals"
        ) VALUES (
            %(rate_id)s,
            %(magn_id)s,
            %(equals)s
        )
    '''
    write_cur = conn.cursor()
    for record in cur:
        record = dict(zip(column_names, record))
        magn_rate = {
            'rate_id': record['rate_id'],
            'magn_id': record['magn_id'],
            'equals': record['equals'],
        }
        write_cur.execute(insert_stmt, magn_rate)

    # set limiting mggnitude
    cur.execute('UPDATE magnitude SET lim_mag = NULL')
    cur.execute('''
        WITH limiting_magnitudes AS (
            SELECT rm.magn_id, sum(r.t_eff*r.lim_mag)/sum(r.t_eff) as lim_mag
            FROM rate r
            INNER JOIN rate_magnitude rm ON rm.rate_id = r.id
            GROUP BY rm.magn_id
        )
        SELECT magn_id, round(lim_mag*100)/100.0 as lim_mag
        FROM limiting_magnitudes
    ''')
    column_names = [desc[0] for desc in cur.description]
    update_stmt = 'UPDATE magnitude SET lim_mag = %s WHERE id = %s'
    for record in cur:
        record = dict(zip(column_names, record))
        write_cur.execute(update_stmt, (record['lim_mag'], record['magn_id'],))

    write_cur.close()
    cur.close()


@connection_decorator
def create_r_views(conn):
    cur = conn.cursor()
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        cur.execute('''
            CREATE OR REPLACE VIEW r_rate AS
                SELECT
                    r.id as "rate.id",
                    r.shower as "shower.code",
                    r.period_start as "period.start",
                    r.period_end as "period.end",
                    r.sl_start as "sl.start",
                    r.sl_end as "sl.end",
                    r.session_id as "session.id",
                    r.observer_id as "observer.id",
                    r.freq as "freq",
                    r.lim_mag as "magn.limit",
                    r.t_eff as "t.eff",
                    r.f as "f",
                    r.t_zenith as "t.zenith",
                    r.rad_alt as "radiant.alt",
                    rm.magn_id as "magn.id"
                FROM rate as r
                LEFT JOIN rate_magnitude rm ON
                    r.id = rm.rate_id
        ''')
        cur.execute('''
            CREATE OR REPLACE VIEW r_magnitude AS
                SELECT
                    id as "magn.id",
                    shower as "shower.code",
                    period_start as "period.start",
                    period_end as "period.end",
                    sl_start as "sl.start",
                    sl_end as "sl.end",
                    session_id as "session.id",
                    observer_id as "observer.id",
                    freq as "freq",
                    mean as "magn.mean",
                    lim_mag as "magn.limit"
                FROM magnitude
        ''')
        cur.execute('''
            CREATE OR REPLACE VIEW r_magnitude_detail AS
                SELECT
                    id as "magn.id",
                    magn as "magn.m",
                    freq as "freq"
                FROM magnitude_detail
        ''')
    cur.close()
