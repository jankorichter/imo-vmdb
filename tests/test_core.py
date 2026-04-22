import logging
from pathlib import Path

import pytest

import imo_vmdb
from imo_vmdb import CSVImporter
from imo_vmdb.db import DBAdapter

FIXTURES = Path(__file__).parent / 'fixtures'
logger = logging.getLogger('test')


class TestInitdb:
    def test_returns_zero(self, fresh_db):
        result = imo_vmdb.initdb(fresh_db, logger)
        assert result == 0

    def test_creates_core_tables(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        fresh_db.commit()
        cur = fresh_db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        for expected in ('obs_session', 'rate', 'magnitude', 'shower', 'radiant'):
            assert expected in tables

    def test_imports_reference_showers(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute('SELECT COUNT(*) FROM shower')
        assert cur.fetchone()[0] > 0

    def test_imports_reference_radiants(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute('SELECT COUNT(*) FROM radiant')
        assert cur.fetchone()[0] > 0


class TestCleanup:
    def test_returns_zero(self, seeded_db):
        result = imo_vmdb.cleanup(seeded_db, logger)
        assert result == 0

    def test_clears_imported_tables(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()

        cur = seeded_db.cursor()
        for table in ('imported_session', 'imported_rate', 'imported_magnitude'):
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            assert cur.fetchone()[0] == 0, f'{table} should be empty after cleanup'

    def test_preserves_reference_data(self, seeded_db):
        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()
        cur = seeded_db.cursor()
        cur.execute('SELECT COUNT(*) FROM shower')
        assert cur.fetchone()[0] > 0


class TestCSVImporter:
    def test_import_sessions(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'sessions.csv')])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_rates(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'rates.csv')])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_magnitudes(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'magnitudes.csv')])
        assert not importer.has_errors
        assert importer.counter_write >= 1

    def test_nonexistent_file_sets_error(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run(['/tmp/no_such_file_xyz_abc.csv'])
        assert importer.has_errors

    def test_unknown_csv_format_sets_error(self, seeded_db, tmp_path):
        bad = tmp_path / 'bad.csv'
        bad.write_text('col_a;col_b\n1;2\n')
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(bad)])
        assert importer.has_errors

    def test_do_delete_replaces_previous_data(self, seeded_db):
        importer1 = CSVImporter(seeded_db, logger)
        importer1.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        importer2 = CSVImporter(seeded_db, logger, do_delete=True)
        importer2.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        cur = seeded_db.cursor()
        cur.execute('SELECT COUNT(*) FROM imported_session')
        assert cur.fetchone()[0] == 2

    def test_multiple_files_in_one_run(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([
            str(FIXTURES / 'sessions.csv'),
            str(FIXTURES / 'rates.csv'),
        ])
        assert not importer.has_errors
        assert importer.counter_write == 4
