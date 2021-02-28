import warnings


class BaseNormalizer(object):

    def __init__(self, db_conn, logger, drop_tables):
        self.db_conn = db_conn
        self.logger = logger
        self.drop_tables = drop_tables
        self.has_errors = False
        self.counter_read = 0
        self.counter_write = 0

    def _log_error(self, msg):
        self.logger.error(msg)
        self.has_errors = True


def create_tables(db_conn, drop_tables):
    cur = db_conn.cursor()

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        if drop_tables:
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS rate_magnitude'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS magnitude_detail'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS magnitude'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS rate'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS obs_session'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE IF NOT EXISTS obs_session
            (
                id integer PRIMARY KEY,
                observer_id integer NULL,
                longitude real NOT NULL,
                latitude real NOT NULL,
                elevation real NOT NULL
            );
        '''))

        cur.execute(db_conn.convert_stmt('''
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
                rad_alt double precision NULL,
                rad_corr double precision NULL,
                CONSTRAINT rate_pkey PRIMARY KEY (id),
                CONSTRAINT rate_session_fk FOREIGN KEY (session_id)
                    REFERENCES obs_session(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))

        if drop_tables:
            cur.execute(
                db_conn.convert_stmt(
                    'CREATE INDEX rate_period_shower_key ON rate(period_start, period_end, shower)'
                )
            )

        cur.execute(db_conn.convert_stmt('''
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
                CONSTRAINT magnitude_pkey PRIMARY KEY (id),
                CONSTRAINT magnitude_session_fk FOREIGN KEY (session_id)
                    REFERENCES obs_session(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))

        if drop_tables:
            cur.execute(
                db_conn.convert_stmt(
                    'CREATE INDEX magnitude_period_shower_key ON rate(period_start, period_end, shower)'
                )
            )

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE IF NOT EXISTS magnitude_detail (
                id integer NOT NULL,
                magn integer NOT NULL,
                freq real NOT NULL,
                CONSTRAINT magnitude_detail_pkey PRIMARY KEY (id, magn),
                CONSTRAINT magnitude_detail_fk FOREIGN KEY (id)
                    REFERENCES magnitude(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))

        if drop_tables:
            cur.execute(
                db_conn.convert_stmt(
                    'CREATE INDEX fki_magnitude_detail_fk ON magnitude_detail(id)'
                )
            )

        cur.execute(db_conn.convert_stmt('''
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
            )'''))

        cur.execute(db_conn.convert_stmt('DELETE FROM rate_magnitude'))

        if drop_tables:
            cur.execute(
                db_conn.convert_stmt(
                    'CREATE INDEX fki_rate_magnitude_magn_fk ON rate_magnitude(magn_id)'
                )
            )

    cur.close()


def create_rate_magn(db_conn):
    cur = db_conn.cursor()

    # find magnitude-rate-pairs containing each other
    cur.execute(db_conn.convert_stmt('''
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
    '''))
    column_names = [desc[0] for desc in cur.description]
    insert_stmt = db_conn.convert_stmt('''
        INSERT INTO rate_magnitude (
            rate_id,
            magn_id,
            "equals"
        ) VALUES (
            %(rate_id)s,
            %(magn_id)s,
            %(equals)s
        )
    ''')
    write_cur = db_conn.cursor()
    for record in cur:
        record = dict(zip(column_names, record))
        magn_rate = {
            'rate_id': record['rate_id'],
            'magn_id': record['magn_id'],
            'equals': record['equals'],
        }
        write_cur.execute(insert_stmt, magn_rate)

    # set limiting mggnitude
    cur.execute(db_conn.convert_stmt('UPDATE magnitude SET lim_mag = NULL'))
    cur.execute(db_conn.convert_stmt('''
        WITH limiting_magnitudes AS (
            SELECT rm.magn_id, sum(r.t_eff*r.lim_mag)/sum(r.t_eff) as lim_mag
            FROM rate r
            INNER JOIN rate_magnitude rm ON rm.rate_id = r.id
            GROUP BY rm.magn_id
        )
        SELECT magn_id, round(lim_mag*100)/100.0 as lim_mag
        FROM limiting_magnitudes
    '''))
    column_names = [desc[0] for desc in cur.description]
    update_stmt = db_conn.convert_stmt(
        'UPDATE magnitude SET lim_mag = %(lim_mag)s WHERE id = %(magn_id)s'
    )
    for record in cur:
        record = dict(zip(column_names, record))
        write_cur.execute(update_stmt, {
            'lim_mag': record['lim_mag'],
            'magn_id': record['magn_id']
        })

    write_cur.close()
    cur.close()
