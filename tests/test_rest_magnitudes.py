"""HTTP-level tests for /api/v1/magnitudes and /api/v1/magnitudes/{id}."""

_BASE = "/api/v1"


class TestMagnitudesList:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes")
        assert r.status_code == 200

    def test_content_type_is_json(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes")
        assert r.content_type == "application/json"

    def test_observations_key_present(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes").get_json()
        assert "observations" in data
        assert len(data["observations"]) > 0

    def test_sessions_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes").get_json()
        assert "sessions" not in data

    def test_magnitude_details_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes").get_json()
        assert "magnitude_details" not in data

    def test_no_db_returns_503(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/magnitudes")
        assert r.status_code == 503


class TestMagnitudesFilters:
    def test_shower_filter_returns_only_matching(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?shower=PER").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?sl_min=139&sl_max=142").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_invalid_sl_min_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes?sl_min=abc")
        assert r.status_code == 400
        assert "error" in r.get_json()


class TestMagnitudesIncludes:
    def test_include_sessions(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?include=sessions").get_json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0

    def test_include_magnitude_details(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/magnitudes?include=magnitude_details"
        ).get_json()
        assert "magnitude_details" in data
        assert len(data["magnitude_details"]) > 0
        first = data["magnitude_details"][0]
        assert "magn" in first
        assert "freq" in first

    def test_legacy_include_magnitudes_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes?include=magnitudes")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_unknown_include_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes?include=evil")
        assert r.status_code == 400


class TestMagnitudesPagination:
    def test_x_total_count_present(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes")
        assert r.headers.get("X-Total-Count") == "2"

    def test_limit_zero_returns_count_only(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes?limit=0")
        data = r.get_json()
        assert data["observations"] == []
        assert r.headers.get("X-Total-Count") == "2"


class TestMagnitudeSingle:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes/1")
        assert r.status_code == 200
        assert r.get_json()["id"] == 1

    def test_unknown_returns_404(self, obs_client):
        assert obs_client.get(f"{_BASE}/magnitudes/999").status_code == 404

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/magnitudes/1").status_code == 503
