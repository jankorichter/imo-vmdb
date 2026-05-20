"""Unit tests for JobManager (imo_vmdb.webui.jobs)."""

import time

from imo_vmdb.webui.jobs import JobManager


class TestJobManager:
    def _wait_for_job(self, jm, job_id, timeout=10.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = jm.get_status(job_id)
            assert status is not None
            if not status["running"]:
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
        assert job_id is not None
        status = jm.get_status(job_id)
        assert status is not None
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
        assert job_id is not None
        self._wait_for_job(jm, job_id)
        status = jm.get_status(job_id)
        assert status is not None
        assert status["exit_code"] == 0

    def test_iter_logs_yields_strings(self, db_conn_factory):
        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        assert job_id is not None
        logs = jm.iter_logs(job_id)
        assert logs is not None
        lines = list(logs)
        assert len(lines) > 0
        assert all(isinstance(line, str) for line in lines)

    def test_start_export_writes_csv(self, db_conn_factory, tmp_path):
        import os

        jm = JobManager()
        job_id = jm.start_initdb(db_conn_factory)
        self._wait_for_job(jm, job_id)

        out = str(tmp_path / "shower.csv")
        job_id = jm.start_export(db_conn_factory, "shower", out)
        assert job_id is not None
        self._wait_for_job(jm, job_id)
        status = jm.get_status(job_id)
        assert status is not None
        assert status["exit_code"] == 0
        assert os.path.isfile(out)
        content = open(out).read()
        assert "iau_code" in content
