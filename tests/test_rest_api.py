"""HTTP-level integration tests for the /api/v1/* REST endpoints."""

_BASE = "/api/v1"


class TestShowersHttp:
    def test_returns_200(self, client):
        r = client.get(f"{_BASE}/showers")
        assert r.status_code == 200

    def test_content_type_is_json(self, client):
        r = client.get(f"{_BASE}/showers")
        assert r.content_type == "application/json"

    def test_returns_non_empty_list(self, client):
        data = client.get(f"{_BASE}/showers").get_json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_shower_fields_present(self, client):
        shower = client.get(f"{_BASE}/showers").get_json()[0]
        for key in (
            "iau_code",
            "name",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
        ):
            assert key in shower

    def test_no_db_returns_503(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/showers")
        assert r.status_code == 503


class TestRatesHttp:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates")
        assert r.status_code == 200

    def test_content_type_is_json(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates")
        assert r.content_type == "application/json"

    def test_observations_key_present(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        assert "observations" in data
        assert len(data["observations"]) > 0

    def test_sessions_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        assert "sessions" not in data

    def test_magnitudes_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        assert "magnitudes" not in data

    def test_shower_filter_returns_only_matching(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?shower=PER").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert showers == ["PER"]

    def test_shower_filter_excludes_others(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?shower=GEM").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert "PER" not in showers

    def test_sl_range_restricts_results(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?sl_min=139&sl_max=142").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_lim_magn_min_restricts_results(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?lim_magn_min=6.0").get_json()
        assert all(o["lim_mag"] >= 6.0 for o in data["observations"])
        assert len(data["observations"]) == 1

    def test_include_sessions(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?include=sessions").get_json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0
        assert "id" in data["sessions"][0]

    def test_include_magnitudes(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?include=magnitudes").get_json()
        assert "magnitudes" in data
        assert len(data["magnitudes"]) > 0
        assert "magn" in data["magnitudes"][0]

    def test_include_both(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?include=sessions,magnitudes").get_json()
        assert "sessions" in data
        assert "magnitudes" in data

    def test_invalid_sl_min_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?sl_min=abc")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_no_db_returns_503(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/rates")
        assert r.status_code == 503


class TestMagnitudesHttp:
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

    def test_magnitudes_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes").get_json()
        assert "magnitudes" not in data

    def test_shower_filter_returns_only_matching(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?shower=PER").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?sl_min=139&sl_max=142").get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_include_sessions(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?include=sessions").get_json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0

    def test_include_magnitudes(self, obs_client):
        data = obs_client.get(f"{_BASE}/magnitudes?include=magnitudes").get_json()
        assert "magnitudes" in data
        assert len(data["magnitudes"]) > 0

    def test_invalid_sl_min_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/magnitudes?sl_min=abc")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_no_db_returns_503(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/magnitudes")
        assert r.status_code == 503
