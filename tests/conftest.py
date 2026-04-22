import configparser
import logging
import tempfile

import pytest

import imo_vmdb
from imo_vmdb.db import DBAdapter

logger = logging.getLogger('test')


@pytest.fixture
def fresh_db(tmp_path):
    """Empty SQLite DB (tables not yet created) — use for testing initdb itself."""
    db_conn = DBAdapter({'database': str(tmp_path / 'fresh.db')})
    yield db_conn
    db_conn.close()


@pytest.fixture
def seeded_db(tmp_path):
    """SQLite DB with tables and reference data (showers, radiants), fresh per test."""
    db_conn = DBAdapter({'database': str(tmp_path / 'seeded.db')})
    imo_vmdb.initdb(db_conn, logger)
    db_conn.commit()
    yield db_conn
    db_conn.close()


@pytest.fixture(scope='session')
def _app_db_path(tmp_path_factory):
    """Single SQLite DB file shared across all Flask-based tests."""
    path = str(tmp_path_factory.mktemp('flask') / 'app.db')
    db_conn = DBAdapter({'database': path})
    imo_vmdb.initdb(db_conn, logging.getLogger('setup'))
    db_conn.commit()
    db_conn.close()
    return path


@pytest.fixture(scope='session')
def app(_app_db_path):
    cfg = configparser.ConfigParser()
    cfg.add_section('database')
    cfg.set('database', 'database', _app_db_path)

    from imo_vmdb.webui import create_app
    flask_app = create_app(cfg, tempfile.gettempdir())
    flask_app.config['TESTING'] = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
