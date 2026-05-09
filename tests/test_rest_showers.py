"""HTTP-level tests for /api/v1/showers, /showers/{code}, /showers/active and
/showers/{code}/radiants."""

_BASE = "/api/v1"


class TestShowersList:
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


class TestShowerSingle:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/showers/PER")
        assert r.status_code == 200
        assert r.get_json()["iau_code"] == "PER"

    def test_unknown_returns_404(self, obs_client):
        assert obs_client.get(f"{_BASE}/showers/ZZZ").status_code == 404

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/showers/PER").status_code == 503


class TestActiveShowers:
    def test_in_period_includes_per(self, obs_client):
        codes = [
            s["iau_code"]
            for s in obs_client.get(
                f"{_BASE}/showers/active?date=2024-08-12"
            ).get_json()
        ]
        assert "PER" in codes

    def test_outside_period_excludes_per(self, obs_client):
        codes = [
            s["iau_code"]
            for s in obs_client.get(
                f"{_BASE}/showers/active?date=2024-05-01"
            ).get_json()
        ]
        assert "PER" not in codes

    def test_invalid_date_returns_400(self, obs_client):
        assert (
            obs_client.get(f"{_BASE}/showers/active?date=not-a-date").status_code == 400
        )

    def test_default_date_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/showers/active")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/showers/active").status_code == 503


class TestShowerRadiants:
    def test_returns_sorted_entries(self, obs_client):
        r = obs_client.get(f"{_BASE}/showers/PER/radiants")
        assert r.status_code == 200
        radiants = r.get_json()
        assert len(radiants) > 0
        keys = [(x["month"], x["day"]) for x in radiants]
        assert keys == sorted(keys)

    def test_unknown_shower_returns_empty(self, obs_client):
        r = obs_client.get(f"{_BASE}/showers/ZZZ/radiants")
        assert r.status_code == 200
        assert r.get_json() == []

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/showers/PER/radiants").status_code == 503
