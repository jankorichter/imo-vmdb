"""Tests for CSVImporter (public API)."""

import logging
from pathlib import Path

from imo_vmdb import CSVImporter

FIXTURES = Path(__file__).parent / "fixtures"
logger = logging.getLogger("test")


class TestCSVImporter:
    def test_import_sessions(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "sessions.csv")])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_rates(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "rates.csv")])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_magnitudes(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "magnitudes.csv")])
        assert not importer.has_errors
        assert importer.counter_write >= 1

    def test_nonexistent_file_sets_error(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run(["/tmp/no_such_file_xyz_abc.csv"])
        assert importer.has_errors

    def test_unknown_csv_format_sets_error(self, seeded_db, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("col_a;col_b\n1;2\n")
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(bad)])
        assert importer.has_errors

    def test_do_delete_replaces_previous_data(self, seeded_db):
        importer1 = CSVImporter(seeded_db, logger)
        importer1.run([str(FIXTURES / "sessions.csv")])
        seeded_db.commit()

        importer2 = CSVImporter(seeded_db, logger, do_delete=True)
        importer2.run([str(FIXTURES / "sessions.csv")])
        seeded_db.commit()

        cur = seeded_db.cursor()
        cur.execute("SELECT COUNT(*) FROM imported_session")
        assert cur.fetchone()[0] == 2

    def test_multiple_files_in_one_run(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run(
            [
                str(FIXTURES / "sessions.csv"),
                str(FIXTURES / "rates.csv"),
            ]
        )
        assert not importer.has_errors
        assert importer.counter_write == 4

    def test_import_sessions_canonical(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "sessions_canonical.csv")])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_rates_canonical(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "rates_canonical.csv")])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_magnitudes_canonical(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "magnitudes_canonical.csv")])
        assert not importer.has_errors
        assert importer.counter_write >= 1

    def test_duplicate_column_sets_error(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / "sessions_duplicate_column.csv")])
        assert importer.has_errors
