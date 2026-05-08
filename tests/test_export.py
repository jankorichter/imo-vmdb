"""Tests for export_table (public API)."""

import pytest

from imo_vmdb import export_table


class TestExportTable:
    def test_shower_returns_columns_and_rows(self, seeded_db):
        cols, rows = export_table(seeded_db, "shower")
        assert isinstance(cols, list)
        assert "iau_code" in cols
        assert len(rows) > 0

    def test_empty_table_has_columns_but_no_rows(self, schema_db):
        cols, rows = export_table(schema_db, "obs_session")
        assert isinstance(cols, list)
        assert len(cols) > 0
        assert rows == []

    def test_returns_tuple(self, seeded_db):
        result = export_table(seeded_db, "shower")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_invalid_table_raises_value_error(self, seeded_db):
        with pytest.raises(ValueError):
            export_table(seeded_db, "no_such_table")


class TestExportTableReimport:
    def test_shower_returns_reimport_compatible_columns(self, seeded_db):
        cols, _ = export_table(seeded_db, "shower", reimport=True)
        required = {
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
        }
        assert required.issubset(set(cols))

    def test_shower_returns_rows(self, seeded_db):
        _, rows = export_table(seeded_db, "shower", reimport=True)
        assert len(rows) > 0

    def test_shower_date_columns_are_strings(self, seeded_db):
        cols, rows = export_table(seeded_db, "shower", reimport=True)
        start_idx = cols.index("start")
        for row in rows:
            assert isinstance(row[start_idx], str)

    def test_shower_no_raw_month_day_columns(self, seeded_db):
        cols, _ = export_table(seeded_db, "shower", reimport=True)
        for col in (
            "start_month",
            "start_day",
            "end_month",
            "end_day",
            "peak_month",
            "peak_day",
            "dec",
        ):
            assert col not in cols

    def test_other_table_reimport_flag_is_noop(self, seeded_db):
        cols_normal, _ = export_table(seeded_db, "radiant")
        cols_reimport, _ = export_table(seeded_db, "radiant", reimport=True)
        assert cols_normal == cols_reimport
