"""Tests for the framework-agnostic imo_vmdb.server Python API."""

import time

from imo_vmdb import export_table
from imo_vmdb.server import (
    JobManager,
    MagnitudeFilter,
    RateFilter,
    query_magnitudes,
    query_rates,
    query_showers,
)


class TestQueryShowers:
    def test_returns_non_empty_list(self, seeded_db):
        result = query_showers(seeded_db)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_items_have_expected_fields(self, seeded_db):
        result = query_showers(seeded_db)
        shower = result[0]
        for field in (
            "iau_code",
            "name",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
        ):
            assert field in shower


class TestQueryRates:
    def test_returns_dict_with_observations(self, seeded_db):
        result = query_rates(seeded_db, RateFilter())
        assert "observations" in result
        assert isinstance(result["observations"], list)

    def test_include_sessions_adds_key(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_sessions=True))
        assert "sessions" in result

    def test_include_magnitudes_adds_key(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_magnitudes=True))
        assert "magnitudes" in result

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER"]))
        assert "observations" in result

    def test_sporadic_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["SPO"]))
        assert "observations" in result

    def test_multi_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER", "GEM"]))
        assert "observations" in result

    def test_numeric_filters_do_not_error(self, seeded_db):
        result = query_rates(
            seeded_db, RateFilter(sl_min=130.0, sl_max=150.0, lim_magn_min=5.0)
        )
        assert "observations" in result

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["PER"]))
        showers = [r["shower"] for r in result["observations"]]
        assert showers == ["PER"]

    def test_shower_filter_excludes_others(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["GEM"]))
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" not in showers

    def test_sl_range_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(sl_min=139.0, sl_max=142.0))
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_lim_magn_min_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(lim_magn_min=6.0))
        lim_mags = [r["lim_mag"] for r in result["observations"]]
        assert all(m >= 6.0 for m in lim_mags)
        assert len(lim_mags) == 1

    def test_include_sessions_returns_session_content(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        assert len(result["sessions"]) > 0
        assert "id" in result["sessions"][0]


class TestQueryMagnitudes:
    def test_returns_dict_with_observations(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter())
        assert "observations" in result
        assert isinstance(result["observations"], list)

    def test_include_sessions_adds_key(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_sessions=True))
        assert "sessions" in result

    def test_include_magnitudes_adds_key(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_magnitudes=True))
        assert "magnitudes" in result

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(showers=["PER"]))
        assert "observations" in result

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_magnitudes(observation_db, MagnitudeFilter(showers=["PER"]))
        showers = [r["shower"] for r in result["observations"]]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, observation_db):
        result = query_magnitudes(
            observation_db, MagnitudeFilter(sl_min=139.0, sl_max=142.0)
        )
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers


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


class TestJobManager:
    def _wait_for_job(self, jm, job_id, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not jm.get_status(job_id)["running"]:
                return
            time.sleep(0.2)
        raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")

    def test_start_initdb_returns_job_id(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        assert isinstance(job_id, str) and len(job_id) > 0
        self._wait_for_job(jm, job_id)

    def test_get_status_returns_dict_with_expected_keys(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        status = jm.get_status(job_id)
        assert "running" in status
        assert "exit_code" in status
        self._wait_for_job(jm, job_id)

    def test_get_status_unknown_job_returns_none(self):
        jm = JobManager()
        assert jm.get_status("no-such-job") is None

    def test_iter_logs_unknown_job_returns_none(self):
        jm = JobManager()
        assert jm.iter_logs("no-such-job") is None

    def test_second_job_blocked_while_first_runs(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        assert job_id is not None
        blocked = jm.start_normalize(db_conn_factory)
        assert blocked is None
        self._wait_for_job(jm, job_id)

    def test_initdb_completes_with_exit_code_zero(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        self._wait_for_job(jm, job_id)
        assert jm.get_status(job_id)["exit_code"] == 0

    def test_iter_logs_yields_strings(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        lines = list(jm.iter_logs(job_id))
        assert len(lines) > 0
        assert all(isinstance(line, str) for line in lines)
