import importlib
import re
import sqlite3
import warnings
from typing import Any

_MONTH_NAMES = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}

_VALID_TABLES = frozenset(
    {
        "shower",
        "radiant",
        "obs_session",
        "imported_session",
        "imported_rate",
        "imported_magnitude",
        "rate",
        "magnitude",
        "rate_magnitude",
        "magnitude_detail",
    }
)

# Tables copied by ``export_db``, in foreign-key-safe insert order.
# Excludes ``imported_*`` tables on purpose: an exported database is meant to be
# shared as a clean snapshot of normalized data.
_EXPORTABLE_DB_TABLES = (
    "shower",
    "radiant",
    "obs_session",
    "rate",
    "magnitude",
    "magnitude_detail",
    "rate_magnitude",
)

_EXPORT_DB_BATCH_SIZE = 1000


class DBException(Exception):
    """Raised when a database operation fails."""


class DBAdapter:
    """Lightweight database connection adapter supporting SQLite, PostgreSQL, and MySQL.

    A dedicated adapter is used instead of a heavier abstraction (e.g. SQLAlchemy)
    because the SQL in this project is straightforward and the only cross-backend
    difference is placeholder syntax.  The adapter handles three concerns:

    * **Dynamic driver selection** — the DB-API 2.0 module (``sqlite3``,
      ``psycopg2``, ``mysql.connector``, …) is imported at runtime from *config*,
      so no specific driver is a hard dependency of the package.
    * **SQLite initialisation** — enables foreign-key enforcement via
      ``PRAGMA foreign_keys = ON``, which SQLite disables by default.
    * **Placeholder normalisation** — see :meth:`convert_stmt`.

    The default backend is ``sqlite3``; a different module can be selected via
    the ``module`` key in *config*.

    :param config: Connection parameters.  The optional ``module`` key names
        the DB-API 2.0 module to load (default: ``"sqlite3"``); all remaining
        keys are forwarded verbatim to that module's ``connect()`` call.

        Typical keys per backend:

        * **SQLite** — ``database``: path to the ``.db`` file.
        * **PostgreSQL** (``module = psycopg2``) — ``database``, ``user``,
          optionally ``host``, ``password``.
        * **MySQL** (``module = pymysql``) — ``database``, ``user``,
          optionally ``host``, ``password``, plus any driver-specific keys
          such as ``sql_mode`` or ``init_command``.

        These correspond directly to the ``[database]`` section of the
        *imo-vmdb* configuration file.
    """

    def __init__(self, config: dict[str, str]) -> None:
        self.db_module = config.get("module", "sqlite3")
        if "module" in config:
            config.pop("module")
        db = importlib.import_module(self.db_module)
        self.conn = db.connect(**config)
        if "sqlite3" == self.db_module:
            self.conn.execute("PRAGMA foreign_keys = ON")

    def cursor(self) -> Any:
        """Return a new database cursor.

        :return: A new cursor object from the underlying DB-API 2.0 connection.
        """
        return self.conn.cursor()

    def commit(self) -> None:
        """Commit the current transaction."""
        self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    def ping(self) -> None:
        """Verify that the database accepts a trivial query.

        Issues a ``SELECT 1`` and discards the result.  Intended for
        liveness/readiness checks (e.g. ``/health`` endpoints).

        :raises DBException: If the underlying driver raises any error.
        """
        try:
            cur = self.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        except Exception as exc:
            raise DBException(str(exc))

    def convert_stmt(self, stmt: str) -> str:
        """Convert a SQL statement to the active backend's dialect.

        SQLite requires ``:name`` placeholders; this method rewrites
        ``%(name)s`` to ``:name`` and replaces ``%%`` with ``%``.
        PostgreSQL (psycopg2) and MySQL (mysql-connector-python) accept
        ``%(name)s`` natively, so their statements are returned unchanged.

        :param stmt: SQL statement using ``%(name)s``-style named placeholders.
        :return: Dialect-adjusted SQL statement.
        """
        if "sqlite3" == self.db_module:
            stmt = stmt.replace(" %% ", " % ")
            return re.sub("%\\(([^)]*)\\)s", ":\\1", stmt)

        return stmt

    def year_expr(self, col: str) -> str:
        """Return a SQL fragment that extracts the year from a timestamp column.

        Cross-dialect helper used by aggregate queries that need to group
        observations by year.  Result type is integer.

        :param col: SQL column reference (e.g. ``"r.period_start"``).
        :return: Dialect-specific SQL expression yielding an integer year.
        """
        if "sqlite3" == self.db_module:
            return f"CAST(strftime('%Y', {col}) AS INTEGER)"
        if self.db_module.startswith("psycopg"):
            return f"EXTRACT(YEAR FROM {col})::int"
        return f"YEAR({col})"


def create_tables(db_conn: "DBAdapter") -> None:
    """Create the full database schema, dropping all existing tables first.

    Builds the tables ``obs_session``, ``rate``, ``magnitude``,
    ``magnitude_detail``, ``rate_magnitude``, ``shower``, ``radiant``,
    ``imported_session``, ``imported_rate``, and ``imported_magnitude``.

    :param db_conn: An open :class:`DBAdapter` connection.
    :raises DBException: If any DDL statement fails.
    """
    cur = db_conn.cursor()

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS rate_magnitude"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS magnitude_detail"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS rate"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS magnitude"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS obs_session"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS shower"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS radiant"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS imported_session"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS imported_rate"))
            cur.execute(db_conn.convert_stmt("DROP TABLE IF EXISTS imported_magnitude"))

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )
        cur.execute(
            db_conn.convert_stmt(
                "CREATE INDEX rate_period_shower_key ON rate(period_start, period_end, shower)"
            )
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )
        cur.execute(
            db_conn.convert_stmt(
                "CREATE INDEX magnitude_period_shower_key ON rate(period_start, period_end, shower)"
            )
        )

        cur.execute(
            db_conn.convert_stmt("""
            CREATE TABLE magnitude_detail (
                id integer NOT NULL,
                magn integer NOT NULL,
                freq real NOT NULL,
                CONSTRAINT magnitude_detail_pkey PRIMARY KEY (id, magn),
                CONSTRAINT magnitude_detail_fk FOREIGN KEY (id)
                    REFERENCES magnitude(id) MATCH SIMPLE
                    ON UPDATE CASCADE
                    ON DELETE CASCADE
            )""")
        )
        cur.execute(
            db_conn.convert_stmt(
                "CREATE INDEX fki_magnitude_detail_fk ON magnitude_detail(id)"
            )
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )
        cur.execute(
            db_conn.convert_stmt(
                "CREATE INDEX fki_rate_magnitude_magn_fk ON rate_magnitude(magn_id)"
            )
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )

        cur.execute(
            db_conn.convert_stmt("""
            CREATE TABLE radiant
            (
                shower char(3) NOT NULL,
                "month" integer NOT NULL,
                "day" integer NOT NULL,
                ra real NOT NULL,
                "dec" real NOT NULL,
                CONSTRAINT radiant_pkey PRIMARY KEY (shower, "month", "day")
            )""")
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )
        cur.execute(
            db_conn.convert_stmt("""
            CREATE INDEX imported_rate_order_key ON
                imported_rate(
                    session_id,
                    shower,
                    "start",
                    "end"
                )
        """)
        )

        cur.execute(
            db_conn.convert_stmt("""
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
            )""")
        )
        cur.execute(
            db_conn.convert_stmt("""
            CREATE INDEX imported_magnitude_order_key ON
                imported_magnitude(
                    session_id,
                    shower,
                    "start",
                    "end"
                )
        """)
        )

        cur.close()
    except Exception as e:
        raise DBException(str(e))


def _format_date(month: int | None, day: int | None) -> str:
    """Format a month/day pair as an abbreviated month name and day number.

    :param month: Month as an integer (1–12), or ``None``.
    :param day: Day as an integer, or ``None``.
    :return: Formatted string such as ``'Aug 12'``, or an empty string if
        either value is ``None``.
    """
    if month is None or day is None:
        return ""
    return f"{_MONTH_NAMES[month]} {day}"


def export_table(
    db_conn: DBAdapter, table: str, reimport: bool = False
) -> tuple[list[str], list[tuple]]:
    """Export all rows from a database table.

    When *reimport* is ``True`` and *table* is ``'shower'``, the result uses
    column names and date formats that are compatible with :class:`CSVImporter`,
    so the exported CSV can be imported again without modification.  For all
    other tables *reimport* has no effect.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param table: Name of the table to export.  Must be one of the known
        tables: ``shower``, ``radiant``, ``obs_session``, ``imported_session``,
        ``imported_rate``, ``imported_magnitude``, ``rate``, ``magnitude``,
        ``rate_magnitude``, ``magnitude_detail``.
    :param reimport: If ``True``, export in re-import-compatible format where applicable.
    :return: Tuple of ``(column_names, rows)``.
    :raises ValueError: If *table* is not a known table name.
    """
    if table not in _VALID_TABLES:
        raise ValueError(f"Unknown table: {table!r}")
    if reimport and table == "shower":
        return _export_shower_reimport(db_conn)
    cur = db_conn.cursor()
    cur.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return cols, rows


class _SQLiteDB(DBAdapter):
    """Wrap an externally-owned :class:`sqlite3.Connection` as a :class:`DBAdapter`.

    Used internally by :func:`imo_vmdb.export_db` so that helpers such as
    :func:`create_tables` (which expect a ``DBAdapter``) can operate on a
    connection whose lifecycle is managed by the caller.

    Not part of the public API.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.db_module = "sqlite3"
        self.conn = conn
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        # Lifecycle is owned by the caller; do not close the wrapped connection.
        pass


def export_db(src_db_conn: DBAdapter, dst_conn: sqlite3.Connection) -> None:
    """Export normalized observations and reference data into a SQLite database.

    Creates the full imo-vmdb schema on *dst_conn* (dropping any pre-existing
    tables) and copies all rows from the normalized and reference tables of
    *src_db_conn* into it.  The raw ``imported_*`` tables are intentionally
    skipped — an exported database is a clean snapshot of normalized data
    that can be shared and used as the input of a fresh imo-vmdb install.

    The destination connection is committed but not closed; its lifecycle is
    owned by the caller.  This allows in-memory destinations (e.g.
    ``sqlite3.connect(":memory:")``) to be inspected after export.

    :param src_db_conn: Source database connection.  May be SQLite,
        PostgreSQL, or MySQL.
    :param dst_conn: Empty (or to-be-overwritten) SQLite destination
        connection.  Must be a real :class:`sqlite3.Connection`; other
        DB-API drivers are not supported as the destination.
    """
    dst_adapter = _SQLiteDB(dst_conn)
    create_tables(dst_adapter)

    src_cur = src_db_conn.cursor()
    dst_cur = dst_conn.cursor()
    for table in _EXPORTABLE_DB_TABLES:
        src_cur.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in src_cur.description]
        placeholders = ", ".join("?" * len(cols))
        col_list = ", ".join(f'"{c}"' for c in cols)
        insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
        while True:
            batch = src_cur.fetchmany(_EXPORT_DB_BATCH_SIZE)
            if not batch:
                break
            dst_cur.executemany(insert_sql, batch)
    dst_conn.commit()


def _export_shower_reimport(db_conn: DBAdapter) -> tuple[list[str], list[tuple]]:
    """Export the ``shower`` table in a format compatible with :class:`CSVImporter`.

    Converts start/end/peak month–day pairs into ``'Mon DD'`` strings and
    renames the ``dec`` column to ``de`` to match the import CSV schema.

    :param db_conn: Open :class:`DBAdapter` connection.
    :return: Tuple ``(column_names, rows)`` ready for CSV serialisation.
    """
    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, iau_code, name, start_month, start_day, end_month, end_day,"
        ' peak_month, peak_day, ra, "dec", v, r, zhr FROM shower ORDER BY id'
    )
    raw_rows = cur.fetchall()
    cols = [
        "id",
        "iau_code",
        "name",
        "start",
        "end",
        "peak",
        "ra",
        "de",
        "v",
        "r",
        "zhr",
    ]
    rows = [
        (
            id_,
            iau_code,
            name,
            _format_date(start_m, start_d),
            _format_date(end_m, end_d),
            _format_date(peak_m, peak_d),
            ra,
            dec,
            v,
            r,
            zhr,
        )
        for id_, iau_code, name, start_m, start_d, end_m, end_d, peak_m, peak_d, ra, dec, v, r, zhr in raw_rows
    ]
    return cols, rows
