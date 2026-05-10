"""Tests for export_db (public API) and the CLI/HTTP export-DB integration."""

import sqlite3

import pytest

from imo_vmdb import DBAdapter, RateFilter, RateService, export_db
from imo_vmdb.command import export as export_cmd

_NORMALIZED_TABLES = (
    "obs_session",
    "rate",
    "magnitude",
    "magnitude_detail",
    "rate_magnitude",
    "shower",
    "radiant",
)
_IMPORTED_TABLES = ("imported_session", "imported_rate", "imported_magnitude")


class TestExportDbApi:
    def test_export_into_memory_has_full_schema(self, observation_db):
        dst = sqlite3.connect(":memory:")
        try:
            export_db(observation_db, dst)
            tables = {
                row[0]
                for row in dst.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for tbl in _NORMALIZED_TABLES + _IMPORTED_TABLES:
                assert tbl in tables, f"missing table {tbl!r} after export"
        finally:
            dst.close()

    def test_export_into_file(self, observation_db, tmp_path):
        out = tmp_path / "out.sqlite"
        dst = sqlite3.connect(str(out))
        try:
            export_db(observation_db, dst)
        finally:
            dst.close()
        assert out.exists()
        with open(out, "rb") as fh:
            assert fh.read(16) == b"SQLite format 3\x00"

    def test_copies_normalized_rows(self, observation_db):
        dst = sqlite3.connect(":memory:")
        try:
            export_db(observation_db, dst)
            for tbl in _NORMALIZED_TABLES:
                src_count = (
                    observation_db.cursor()
                    .execute(f"SELECT COUNT(*) FROM {tbl}")
                    .fetchone()[0]
                )
                dst_count = dst.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                assert (
                    src_count == dst_count
                ), f"row count mismatch in {tbl}: src={src_count} dst={dst_count}"
        finally:
            dst.close()

    def test_skips_imported_tables(self, imported_db):
        # Sanity: imported_db actually has rows in the raw tables.
        for tbl in _IMPORTED_TABLES:
            n = (
                imported_db.cursor()
                .execute(f"SELECT COUNT(*) FROM {tbl}")
                .fetchone()[0]
            )
            assert n > 0, f"fixture broken: {tbl} is empty"

        dst = sqlite3.connect(":memory:")
        try:
            export_db(imported_db, dst)
            for tbl in _IMPORTED_TABLES:
                n = dst.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                assert n == 0, f"imported_* table {tbl} should be empty in export"
        finally:
            dst.close()

    def test_does_not_close_destination(self, observation_db):
        dst = sqlite3.connect(":memory:")
        try:
            export_db(observation_db, dst)
            # Should still be usable.
            n = dst.execute("SELECT COUNT(*) FROM rate").fetchone()[0]
            assert n == 2
        finally:
            dst.close()

    def test_result_is_reusable_with_imo_vmdb(self, observation_db, tmp_path):
        out = tmp_path / "reuse.sqlite"
        dst = sqlite3.connect(str(out))
        try:
            export_db(observation_db, dst)
        finally:
            dst.close()

        reopened = DBAdapter({"database": str(out)})
        try:
            rates = RateService(reopened).query(RateFilter())
            assert len(rates.observations) == 2
        finally:
            reopened.close()


class TestExportDbCli:
    def _config_file(self, tmp_path, db_path):
        cfg = tmp_path / "config.ini"
        cfg.write_text(f"[database]\ndatabase = {db_path}\n")
        return str(cfg)

    def test_export_db_writes_sqlite_file(self, observation_db, tmp_path):
        observation_db.commit()
        src_path = str(tmp_path / "seeded.db")  # see conftest.seeded_db

        out = tmp_path / "exp.sqlite"
        cfg = self._config_file(tmp_path, src_path)
        export_cmd.main(["db", "-c", cfg, "-o", str(out)])
        assert out.exists()

        with sqlite3.connect(str(out)) as check:
            n = check.execute("SELECT COUNT(*) FROM rate").fetchone()[0]
            assert n == 2

    def test_export_db_without_output_errors(self, tmp_path):
        cfg = self._config_file(tmp_path, str(tmp_path / "nonexistent.db"))
        with pytest.raises(SystemExit):
            export_cmd.main(["db", "-c", cfg])

    def test_export_db_with_reimport_errors(self, tmp_path):
        cfg = self._config_file(tmp_path, str(tmp_path / "nonexistent.db"))
        with pytest.raises(SystemExit):
            export_cmd.main(
                ["db", "-c", cfg, "-o", str(tmp_path / "x.sqlite"), "--reimport"]
            )

    def test_unknown_target_errors(self, tmp_path, capsys):
        with pytest.raises(SystemExit):
            export_cmd.main(["bogus"])
