"""Tests for the core pipeline operations: initdb, cleanup, normalize."""

import logging

import imo_vmdb

logger = logging.getLogger("test")


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
        for expected in ("obs_session", "rate", "magnitude", "shower", "radiant"):
            assert expected in tables

    def test_imports_reference_showers(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute("SELECT COUNT(*) FROM shower")
        assert cur.fetchone()[0] > 0

    def test_imports_reference_radiants(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute("SELECT COUNT(*) FROM radiant")
        assert cur.fetchone()[0] > 0


class TestCleanup:
    def test_returns_zero(self, seeded_db):
        result = imo_vmdb.cleanup(seeded_db, logger)
        assert result == 0

    def test_clears_imported_tables(self, seeded_db):
        from pathlib import Path

        from imo_vmdb import CSVImporter

        fixtures = Path(__file__).parent / "fixtures"
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(fixtures / "sessions.csv")])
        seeded_db.commit()

        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()

        cur = seeded_db.cursor()
        for table in ("imported_session", "imported_rate", "imported_magnitude"):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            assert cur.fetchone()[0] == 0, f"{table} should be empty after cleanup"

    def test_preserves_reference_data(self, seeded_db):
        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()
        cur = seeded_db.cursor()
        cur.execute("SELECT COUNT(*) FROM shower")
        assert cur.fetchone()[0] > 0


class TestNormalize:
    def test_returns_zero(self, imported_db):
        result = imo_vmdb.normalize(imported_db, logger)
        assert result == 0

    def test_populates_obs_session(self, imported_db):
        imo_vmdb.normalize(imported_db, logger)
        imported_db.commit()
        cur = imported_db.cursor()
        cur.execute("SELECT COUNT(*) FROM obs_session")
        assert cur.fetchone()[0] > 0

    def test_populates_rate(self, imported_db):
        imo_vmdb.normalize(imported_db, logger)
        imported_db.commit()
        cur = imported_db.cursor()
        cur.execute("SELECT COUNT(*) FROM rate")
        assert cur.fetchone()[0] > 0

    def test_populates_magnitude(self, imported_db):
        imo_vmdb.normalize(imported_db, logger)
        imported_db.commit()
        cur = imported_db.cursor()
        cur.execute("SELECT COUNT(*) FROM magnitude")
        assert cur.fetchone()[0] > 0

    def test_idempotent(self, imported_db):
        imo_vmdb.normalize(imported_db, logger)
        imported_db.commit()
        cur = imported_db.cursor()
        cur.execute("SELECT COUNT(*) FROM obs_session")
        count_first = cur.fetchone()[0]

        imo_vmdb.normalize(imported_db, logger)
        imported_db.commit()
        cur.execute("SELECT COUNT(*) FROM obs_session")
        count_second = cur.fetchone()[0]

        assert count_first == count_second
