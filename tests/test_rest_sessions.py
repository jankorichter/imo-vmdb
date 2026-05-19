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
            f"{_BASE}/sessions?period_start=2023-01-01T00:00:00"
            f"&period_end=2023-12-31T23:59:59"
        ).get_json()
        assert len(data["sessions"]) == 1

    def test_period_filter_excludes_outside(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/sessions?period_start=2030-01-01T00:00:00"
            f"&period_end=2030-12-31T23:59:59"
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


class TestSessionsFilters:
    """Observation-level filters resolved through EXISTS on rate/magnitude."""

    def test_shower_filter_matches(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?shower=PER").get_json()
        assert len(data["sessions"]) == 1

    def test_shower_filter_no_match(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?shower=LEO").get_json()
        assert data["sessions"] == []

    def test_shower_spo_no_match(self, obs_client):
        # Seed data has only PER and GEM rates, no sporadics.
        data = obs_client.get(f"{_BASE}/sessions?shower=SPO").get_json()
        assert data["sessions"] == []

    def test_shower_multi_value_matches(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?shower=PER&shower=GEM").get_json()
        assert len(data["sessions"]) == 1

    def test_sl_range_matches(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?sl_min=139&sl_max=142").get_json()
        assert len(data["sessions"]) == 1

    def test_sl_range_no_match(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?sl_min=300&sl_max=310").get_json()
        assert data["sessions"] == []

    def test_lim_magn_filter(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?lim_magn_min=6.4").get_json()
        assert len(data["sessions"]) == 1
        data = obs_client.get(f"{_BASE}/sessions?lim_magn_min=10").get_json()
        assert data["sessions"] == []

    def test_combined_filters_matches(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/sessions?shower=PER&sl_min=139&sl_max=142&lim_magn_min=6.0"
        ).get_json()
        assert len(data["sessions"]) == 1

    def test_combined_filters_no_match(self, obs_client):
        # PER session exists in sl 139-141, but at lim_magn 6.5; demand >7 → empty.
        data = obs_client.get(
            f"{_BASE}/sessions?shower=PER&lim_magn_min=7.0"
        ).get_json()
        assert data["sessions"] == []

    def test_invalid_sl_min_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions?sl_min=abc")
        assert r.status_code == 400


class TestSessionsIncludes:
    """Full rate/magnitude observations attached via include."""

    def test_include_rates(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?include=rates").get_json()
        assert "rates" in data
        assert len(data["rates"]) == 2
        # Returns full RateObservation rows, not detail.
        assert "sun_alt" in data["rates"][0]

    def test_include_magnitudes_returns_full_observations(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?include=magnitudes").get_json()
        assert "magnitudes" in data
        assert len(data["magnitudes"]) == 2
        # MagnitudeObservation has 'mean', MagnitudeDetail has 'magn'.
        # On /sessions we return full observations, so 'mean' must be present.
        assert "mean" in data["magnitudes"][0]
        assert "magn" not in data["magnitudes"][0]

    def test_include_both(self, obs_client):
        data = obs_client.get(f"{_BASE}/sessions?include=rates,magnitudes").get_json()
        assert "rates" in data and "magnitudes" in data

    def test_include_magnitude_details_returns_400(self, obs_client):
        # magnitude_details is not exposed on /sessions; use /magnitudes instead.
        r = obs_client.get(f"{_BASE}/sessions?include=magnitude_details")
        assert r.status_code == 400
        assert "magnitude_details" in r.get_json()["error"]

    def test_filter_is_inherited_into_include(self, obs_client):
        # PER-only filter → only the PER rate (id=1) should appear in include.
        data = obs_client.get(f"{_BASE}/sessions?shower=PER&include=rates").get_json()
        assert [r["shower"] for r in data["rates"]] == ["PER"]

    def test_unknown_include_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/sessions?include=sessions")
        assert r.status_code == 400
        assert "include" in r.get_json()["error"].lower()
