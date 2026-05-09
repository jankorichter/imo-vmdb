"""HTTP-level tests for /api/v1/stats/* aggregate endpoints."""

_BASE = "/api/v1"


class TestStatsMeta:
    def test_returns_200(self, obs_client):
        data = obs_client.get(f"{_BASE}/stats/meta").get_json()
        assert data["sessions"] == 1
        assert data["rates"] == 2
        assert data["magnitudes"] == 2
        assert data["period_start"].startswith("2023-08-12")
        assert data["period_end"].startswith("2023-12-14")

    def test_empty_db(self, client):
        data = client.get(f"{_BASE}/stats/meta").get_json()
        assert data["rates"] == 0
        assert data["period_start"] is None

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/stats/meta").status_code == 503


class TestStatsByShower:
    def test_returns_per_and_gem(self, obs_client):
        data = obs_client.get(f"{_BASE}/stats/by-shower").get_json()
        codes = {row["shower"] for row in data}
        assert codes == {"PER", "GEM"}

    def test_period_filter(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/stats/by-shower?period_start=2023-08-01&period_end=2023-09-30"
        ).get_json()
        assert {row["shower"] for row in data} == {"PER"}

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/stats/by-shower").status_code == 503


class TestStatsByCountry:
    def test_de_present(self, obs_client):
        data = obs_client.get(f"{_BASE}/stats/by-country").get_json()
        de = next(row for row in data if row["country"] == "DE")
        assert de["sessions"] == 1
        assert de["rates"] == 2

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/stats/by-country").status_code == 503


class TestStatsByYear:
    def test_includes_2023(self, obs_client):
        data = obs_client.get(f"{_BASE}/stats/by-year").get_json()
        years = {row["year"]: row for row in data}
        assert 2023 in years
        assert years[2023]["rates"] == 2

    def test_period_filter_excludes_others(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/stats/by-year?period_start=2030-01-01&period_end=2030-12-31"
        ).get_json()
        assert data == []

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/stats/by-year").status_code == 503
