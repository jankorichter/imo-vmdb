"""Tests for the Web UI HTTP routes (/, /export/*, /run/*, /status/*)."""
import time


def _start_job(client, url, timeout=10.0):
    """POST to a run endpoint, retrying until no other job is running (max timeout)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.post(url)
        if r.status_code == 200:
            return r
        time.sleep(0.1)
    raise TimeoutError(f'No job slot became free within {timeout}s')


class TestIndex:
    def test_returns_200(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_contains_app_title(self, client):
        r = client.get('/')
        assert b'imo-vmdb' in r.data


class TestExport:
    def test_shower_returns_csv(self, client):
        r = client.get('/export/shower')
        assert r.status_code == 200
        assert b';' in r.data

    def test_shower_reimport_returns_original_header(self, client):
        r = client.get('/export/shower?reimport=1')
        assert r.status_code == 200
        assert b'IAU_code' in r.data

    def test_radiant_returns_csv(self, client):
        r = client.get('/export/radiant')
        assert r.status_code == 200
        assert b';' in r.data

    def test_radiant_reimport_returns_original_format(self, client):
        r = client.get('/export/radiant?reimport=1')
        assert r.status_code == 200
        assert b'shower' in r.data

    def test_session_export_returns_200(self, client):
        r = client.get('/export/session')
        assert r.status_code == 200

    def test_rate_export_returns_200(self, client):
        r = client.get('/export/rate')
        assert r.status_code == 200

    def test_magnitude_export_returns_200(self, client):
        r = client.get('/export/magnitude')
        assert r.status_code == 200

    def test_magnitude_detail_export_returns_200(self, client):
        r = client.get('/export/magnitude_detail')
        assert r.status_code == 200

    def test_rate_magnitude_export_returns_200(self, client):
        r = client.get('/export/rate_magnitude')
        assert r.status_code == 200


class TestJobManagement:
    def test_run_initdb_returns_job_id(self, client):
        r = _start_job(client, '/run/initdb')
        data = r.get_json()
        assert 'job_id' in data
        assert isinstance(data['job_id'], str)

    def test_status_of_started_job(self, client):
        r = _start_job(client, '/run/initdb')
        job_id = r.get_json()['job_id']

        r2 = client.get(f'/status/{job_id}')
        assert r2.status_code == 200
        assert 'running' in r2.get_json()

    def test_status_unknown_job_returns_404(self, client):
        r = client.get('/status/no-such-job-xyz')
        assert r.status_code == 404

    def test_job_completes_with_exit_code(self, client):
        r = _start_job(client, '/run/initdb')
        job_id = r.get_json()['job_id']

        for _ in range(50):
            status = client.get(f'/status/{job_id}').get_json()
            if not status['running']:
                break
            time.sleep(0.2)

        assert status['exit_code'] == 0
