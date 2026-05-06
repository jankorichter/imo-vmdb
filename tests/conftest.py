import configparser
import logging
import tempfile

import pytest

import imo_vmdb
from imo_vmdb.db import DBAdapter

logger = logging.getLogger("test")


def _insert_observations(cur):
    """Insert one session, two rate/magnitude pairs and detail rows."""
    cur.execute(
        "INSERT INTO obs_session (id, longitude, latitude, elevation, country, city) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (1, 13.4, 52.5, 50.0, "DE", "Berlin"),
    )

    rate_fields = (
        "id, shower, period_start, period_end, sl_start, sl_end, session_id, "
        "freq, lim_mag, t_eff, f, sidereal_time, sun_alt, sun_az, moon_alt, moon_az, moon_illum"
    )
    cur.execute(
        f"INSERT INTO rate ({rate_fields}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            1,
            "PER",
            "2023-08-12 22:00",
            "2023-08-12 23:00",
            139.5,
            140.5,
            1,
            10,
            6.5,
            1.0,
            1.0,
            180.0,
            -20.0,
            270.0,
            -10.0,
            90.0,
            0.1,
        ),
    )
    cur.execute(
        f"INSERT INTO rate ({rate_fields}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            2,
            "GEM",
            "2023-12-14 22:00",
            "2023-12-14 23:00",
            260.0,
            261.0,
            1,
            5,
            5.5,
            1.0,
            1.0,
            200.0,
            -30.0,
            280.0,
            -5.0,
            95.0,
            0.2,
        ),
    )

    magn_fields = "id, shower, period_start, period_end, sl_start, sl_end, session_id, freq, mean, lim_mag"
    cur.execute(
        f"INSERT INTO magnitude ({magn_fields}) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            1,
            "PER",
            "2023-08-12 22:00",
            "2023-08-12 23:00",
            139.5,
            140.5,
            1,
            50,
            3.2,
            6.5,
        ),
    )
    cur.execute(
        f"INSERT INTO magnitude ({magn_fields}) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            2,
            "GEM",
            "2023-12-14 22:00",
            "2023-12-14 23:00",
            260.0,
            261.0,
            1,
            30,
            2.8,
            5.5,
        ),
    )

    cur.execute(
        "INSERT INTO rate_magnitude (rate_id, magn_id, equals) VALUES (?, ?, ?)",
        (1, 1, 1),
    )
    cur.execute(
        "INSERT INTO rate_magnitude (rate_id, magn_id, equals) VALUES (?, ?, ?)",
        (2, 2, 1),
    )

    cur.execute(
        "INSERT INTO magnitude_detail (id, magn, freq) VALUES (?, ?, ?)", (1, 3, 5.0)
    )
    cur.execute(
        "INSERT INTO magnitude_detail (id, magn, freq) VALUES (?, ?, ?)", (1, 4, 8.0)
    )
    cur.execute(
        "INSERT INTO magnitude_detail (id, magn, freq) VALUES (?, ?, ?)", (2, 2, 3.0)
    )


@pytest.fixture
def fresh_db(tmp_path):
    """Empty SQLite DB (tables not yet created) — use for testing initdb itself."""
    db_conn = DBAdapter({"database": str(tmp_path / "fresh.db")})
    yield db_conn
    db_conn.close()


@pytest.fixture
def seeded_db(tmp_path):
    """SQLite DB with tables and reference data (showers, radiants), fresh per test."""
    db_conn = DBAdapter({"database": str(tmp_path / "seeded.db")})
    imo_vmdb.initdb(db_conn, logger)
    db_conn.commit()
    yield db_conn
    db_conn.close()


@pytest.fixture(scope="session")
def _app_db_path(tmp_path_factory):
    """Single SQLite DB file shared across all Flask-based tests."""
    path = str(tmp_path_factory.mktemp("flask") / "app.db")
    db_conn = DBAdapter({"database": path})
    imo_vmdb.initdb(db_conn, logging.getLogger("setup"))
    db_conn.commit()
    db_conn.close()
    return path


@pytest.fixture(scope="session")
def app(_app_db_path):
    cfg = configparser.ConfigParser()
    cfg.add_section("database")
    cfg.set("database", "database", _app_db_path)

    from imo_vmdb.httpd import create_app

    flask_app = create_app(cfg, tempfile.gettempdir())
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_conn_factory(tmp_path):
    path = str(tmp_path / "job.db")

    def factory():
        return DBAdapter({"database": path})

    return factory


@pytest.fixture
def schema_db(tmp_path):
    """SQLite DB with table schema only — no data at all."""
    from imo_vmdb.db import create_tables

    db_conn = DBAdapter({"database": str(tmp_path / "schema.db")})
    create_tables(db_conn)
    db_conn.commit()
    yield db_conn
    db_conn.close()


@pytest.fixture
def observation_db(seeded_db):
    """seeded_db augmented with one session, two rate and two magnitude records."""
    cur = seeded_db.cursor()
    _insert_observations(cur)
    seeded_db.commit()
    return seeded_db


@pytest.fixture(scope="session")
def _obs_db_path(tmp_path_factory):
    """Session-scoped SQLite DB with observation data for HTTP-level API tests."""
    path = str(tmp_path_factory.mktemp("api") / "api.db")
    db_conn = DBAdapter({"database": path})
    imo_vmdb.initdb(db_conn, logging.getLogger("setup"))
    _insert_observations(db_conn.cursor())
    db_conn.commit()
    db_conn.close()
    return path


@pytest.fixture(scope="session")
def obs_app(_obs_db_path):
    cfg = configparser.ConfigParser()
    cfg.add_section("database")
    cfg.set("database", "database", _obs_db_path)

    from imo_vmdb.httpd import create_app

    flask_app = create_app(cfg, tempfile.gettempdir())
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def obs_client(obs_app):
    return obs_app.test_client()


@pytest.fixture(scope="session")
def no_db_app():
    """Flask app with no database section — triggers 503 responses."""
    from imo_vmdb.httpd import create_app

    flask_app = create_app(configparser.ConfigParser(), tempfile.gettempdir())
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture
def no_db_client(no_db_app):
    return no_db_app.test_client()
