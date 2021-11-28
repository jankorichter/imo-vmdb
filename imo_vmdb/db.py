import importlib
import re
import warnings


class DBException(Exception):
    pass


class DBAdapter(object):

    def __init__(self, config):
        self.db_module = config.get('module', 'sqlite3')
        if 'module' in config:
            config.pop('module')
        db = importlib.import_module(self.db_module)
        self.conn = db.connect(**config)
        if 'sqlite3' == self.db_module:
            self.conn.execute('PRAGMA foreign_keys = ON')

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def convert_stmt(self, stmt):
        if 'sqlite3' == self.db_module:
            stmt = stmt.replace(' %% ', ' % ')
            return re.sub('%\\(([^)]*)\\)s', ':\\1', stmt)

        return stmt


def create_tables(db_conn):
    cur = db_conn.cursor()

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS rate_magnitude'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS magnitude_detail'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS rate'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS magnitude'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS obs_session'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS shower'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS radiant'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_session'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_rate'))
            cur.execute(db_conn.convert_stmt('DROP TABLE IF EXISTS imported_magnitude'))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE obs_session
            (
                id integer PRIMARY KEY,
                longitude real NOT NULL,
                latitude real NOT NULL,
                elevation real NOT NULL,
                observer_id integer NULL,
                observer_name TEXT NULL,
                country TEXT NOT NULL,
                city TEXT NOT NULL
            )'''))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE rate (
                id integer NOT NULL,
                shower varchar(6) NULL,
                period_start timestamp NOT NULL,
                period_end timestamp NOT NULL,
                sl_start double precision NOT NULL,
                sl_end double precision NOT NULL,
                session_id integer NOT NULL,
                freq integer NOT NULL,
                lim_mag real NOT NULL,
                t_eff real NOT NULL,
                f real NOT NULL,
                sidereal_time double precision NOT NULL,
                sun_alt double precision NOT NULL,
                sun_az double precision NOT NULL,
                moon_alt double precision NOT NULL,
                moon_az double precision NOT NULL,
                moon_illum double precision NOT NULL,
                field_alt double precision NULL,
                field_az double precision NULL,
                rad_alt double precision NULL,
                rad_az double precision NULL,
                CONSTRAINT rate_pkey PRIMARY KEY (id),
                CONSTRAINT rate_session_fk FOREIGN KEY (session_id)
                    REFERENCES obs_session(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))
        cur.execute(
            db_conn.convert_stmt(
                'CREATE INDEX rate_period_shower_key ON rate(period_start, period_end, shower)'
            )
        )

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE magnitude (
                id integer NOT NULL,
                shower varchar(6) NULL,
                period_start timestamp NOT NULL,
                period_end timestamp NOT NULL,
                sl_start double precision NOT NULL,
                sl_end double precision NOT NULL,
                session_id integer NOT NULL,
                freq integer NOT NULL,
                mean double precision NOT NULL,
                lim_mag real NULL,
                CONSTRAINT magnitude_pkey PRIMARY KEY (id),
                CONSTRAINT magnitude_session_fk FOREIGN KEY (session_id)
                    REFERENCES obs_session(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))
        cur.execute(
            db_conn.convert_stmt(
                'CREATE INDEX magnitude_period_shower_key ON rate(period_start, period_end, shower)'
            )
        )

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE magnitude_detail (
                id integer NOT NULL,
                magn integer NOT NULL,
                freq real NOT NULL,
                CONSTRAINT magnitude_detail_pkey PRIMARY KEY (id, magn),
                CONSTRAINT magnitude_detail_fk FOREIGN KEY (id)
                    REFERENCES magnitude(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )'''))
        cur.execute(
            db_conn.convert_stmt(
                'CREATE INDEX fki_magnitude_detail_fk ON magnitude_detail(id)'
            )
        )

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE rate_magnitude (
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
        cur.execute(
            db_conn.convert_stmt(
                'CREATE INDEX fki_rate_magnitude_magn_fk ON rate_magnitude(magn_id)'
            )
        )

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE shower (
                id integer NOT NULL,
                iau_code varchar(6) NOT NULL,
                name text NOT NULL,
                start_month integer NOT NULL,
                start_day integer NOT NULL,
                end_month integer NOT NULL,
                end_day integer NOT NULL,
                peak_month integer,
                peak_day integer,
                ra real,
                "dec" real,
                v real,
                r real,
                zhr real,
                CONSTRAINT shower_pkey PRIMARY KEY (id),
                CONSTRAINT shower_iau_code_ukey UNIQUE (iau_code)
            )'''))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE radiant
            (
                shower char(3) NOT NULL,
                "month" integer NOT NULL,
                "day" integer NOT NULL,
                ra real NOT NULL,
                "dec" real NOT NULL,
                CONSTRAINT radiant_pkey PRIMARY KEY (shower, "month", "day")
            )'''))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_session
            (
                id integer PRIMARY KEY,
                observer_id integer NULL,
                observer_name TEXT NULL,
                longitude real NOT NULL,
                latitude real NOT NULL,
                elevation real NULL,
                country TEXT NOT NULL,
                city TEXT NOT NULL
            )'''))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_rate
            (
                id integer NOT NULL,
                observer_id integer NULL,
                session_id integer NOT NULL,
                shower varchar(6) NULL,
                "start" timestamp NOT NULL,
                "end" timestamp NOT NULL,
                t_eff real NOT NULL,
                f real NOT NULL,
                lm real NOT NULL,
                method text NOT NULL,
                ra real,
                "dec" real,
                "number" integer NOT NULL,
                CONSTRAINT imported_rate_pkey PRIMARY KEY (id)
            )'''))
        cur.execute(db_conn.convert_stmt('''
            CREATE INDEX imported_rate_order_key ON
                imported_rate(
                    session_id,
                    shower,
                    "start",
                    "end"
                )
        '''))

        cur.execute(db_conn.convert_stmt('''
            CREATE TABLE imported_magnitude
            (
                id integer NOT NULL,
                observer_id integer NULL,
                session_id integer NOT NULL,
                shower varchar(6) NULL,
                "start" timestamp NOT NULL,
                "end" timestamp NOT NULL,
                magn text NOT NULL,
                CONSTRAINT imported_magnitude_pkey PRIMARY KEY (id)
            )'''))
        cur.execute(db_conn.convert_stmt('''
            CREATE INDEX imported_magnitude_order_key ON
                imported_magnitude(
                    session_id,
                    shower,
                    "start",
                    "end"
                )
        '''))

        cur.close()
    except Exception as e:
        raise DBException(str(e))
