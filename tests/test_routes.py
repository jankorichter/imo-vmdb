"""Tests for the Web UI HTTP routes (/, /export/*, /run/*, /status/*)."""

import configparser
import tempfile
import time

import pytest

from imo_vmdb.httpd import create_app


def _start_job(client, url, timeout=10.0):
    """POST to a run endpoint, retrying until no other job is running (max timeout)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.post(url)
        if r.status_code == 200:
            return r
        time.sleep(0.1)
    raise TimeoutError(f"No job slot became free within {timeout}s")


class TestIndex:
    def test_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_contains_app_title(self, client):
        r = client.get("/")
        assert b"imo-vmdb" in r.data


class TestExport:
    def test_shower_returns_csv(self, client):
        r = client.get("/export/shower")
        assert r.status_code == 200
        assert b";" in r.data

    def test_radiant_returns_csv(self, client):
        r = client.get("/export/radiant")
        assert r.status_code == 200
        assert b";" in r.data

    def test_shower_reimport_has_compatible_columns(self, client):
        r = client.get("/export/shower?reimport=1")
        assert r.status_code == 200
        header = r.data.split(b"\n")[0].decode().strip()
        cols = {c.lower() for c in header.split(";")}
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
        assert required.issubset(cols)

    def test_radiant_reimport_returns_original_format(self, client):
        r = client.get("/export/radiant?reimport=1")
        assert r.status_code == 200
        header = r.data.split(b"\n")[0].decode().strip()
        cols = {c.lower() for c in header.split(";")}
        required = {"shower", "ra", "dec", "day", "month"}
        assert required.issubset(cols)

    def test_session_export_returns_200(self, client):
        r = client.get("/export/session")
        assert r.status_code == 200

    def test_rate_export_returns_200(self, client):
        r = client.get("/export/rate")
        assert r.status_code == 200

    def test_magnitude_export_returns_200(self, client):
        r = client.get("/export/magnitude")
        assert r.status_code == 200

    def test_magnitude_detail_export_returns_200(self, client):
        r = client.get("/export/magnitude_detail")
        assert r.status_code == 200

    def test_rate_magnitude_export_returns_404(self, client):
        # rate_magnitude is no longer an exportable table on 2.0.0
        r = client.get("/export/rate_magnitude")
        assert r.status_code == 404


class TestJobManagement:
    def test_run_initdb_returns_job_id(self, client):
        r = _start_job(client, "/run/initdb")
        data = r.get_json()
        assert "job_id" in data
        assert isinstance(data["job_id"], str)

    def test_status_of_started_job(self, client):
        r = _start_job(client, "/run/initdb")
        job_id = r.get_json()["job_id"]

        r2 = client.get(f"/status/{job_id}")
        assert r2.status_code == 200
        assert "running" in r2.get_json()

    def test_status_unknown_job_returns_404(self, client):
        r = client.get("/status/no-such-job-xyz")
        assert r.status_code == 404

    def test_job_completes_with_exit_code(self, client):
        r = _start_job(client, "/run/initdb")
        job_id = r.get_json()["job_id"]

        for _ in range(50):
            status = client.get(f"/status/{job_id}").get_json()
            if not status["running"]:
                break
            time.sleep(0.2)

        assert status["exit_code"] == 0


class TestWebuiDisabled:
    """When create_app(enable_webui=False), only the REST API is served."""

    @pytest.fixture
    def api_only_client(self, _app_db_path):
        cfg = configparser.ConfigParser()
        cfg.add_section("database")
        cfg.set("database", "database", _app_db_path)
        app = create_app(cfg, tempfile.gettempdir(), enable_webui=False)
        app.config["TESTING"] = True
        return app.test_client()

    def test_index_returns_404(self, api_only_client):
        r = api_only_client.get("/")
        assert r.status_code == 404

    def test_export_returns_404(self, api_only_client):
        r = api_only_client.get("/export/shower")
        assert r.status_code == 404

    def test_rest_api_still_works(self, api_only_client):
        r = api_only_client.get("/api/v1/showers")
        assert r.status_code == 200

    def test_download_db_available_without_webui(self, api_only_client):
        r = api_only_client.get("/download/db")
        assert r.status_code == 200
        assert r.data[:16] == b"SQLite format 3\x00"


class TestDownloadDb:
    def test_returns_sqlite_file(self, obs_client):
        r = obs_client.get("/download/db")
        assert r.status_code == 200
        assert r.headers.get("Content-Disposition", "").startswith("attachment")
        assert "imo_vmdb.sqlite" in r.headers.get("Content-Disposition", "")
        assert r.data[:16] == b"SQLite format 3\x00"

    def test_index_links_to_download_db(self, client):
        r = client.get("/")
        assert b'href="/download/db"' in r.data

    def test_without_db_returns_503(self, no_db_client):
        r = no_db_client.get("/download/db")
        assert r.status_code == 503
