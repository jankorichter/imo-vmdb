"""HTTP-level tests for /api/v1/sessions and /api/v1/sessions/{id}."""

_BASE = "/api/v1"


class TestSessionsList:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions")
        assert r.status_code == 200
        assert "sessions" in r.get_json()

    def test_x_total_count_present(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions")
        assert r.headers.get("X-Total-Count") == "1"

    def test_observer_filter_excludes_when_no_match(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions?observer_id=42")
        assert r.get_json()["sessions"] == []

    def test_period_filter_includes_matching(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/sessions?period_start=2023-01-01&period_end=2023-12-31"
        ).get_json()
        assert len(data["sessions"]) == 1

    def test_period_filter_excludes_outside(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/sessions?period_start=2030-01-01&period_end=2030-12-31"
        ).get_json()
        assert data["sessions"] == []

    def test_limit_zero_count_only(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions?limit=0")
        assert r.get_json()["sessions"] == []
        assert r.headers.get("X-Total-Count") == "1"

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/sessions").status_code == 503


class TestSessionSingle:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions/1")
        assert r.status_code == 200
        assert r.get_json()["id"] == 1

    def test_unknown_returns_404(self, obs_client):
        assert obs_client.get(f"{_BASE}/sessions/999").status_code == 404

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/sessions/1").status_code == 503
