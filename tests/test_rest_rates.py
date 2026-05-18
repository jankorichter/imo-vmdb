"""HTTP-level tests for /api/v1/rates and /api/v1/rates/{id}."""

_BASE = "/api/v1"


class TestRatesList:
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

    def test_observations_expose_magn_id_and_magn_solo(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        linked = [o for o in data["observations"] if o.get("magn_id") is not None]
        assert linked, "expected at least one observation linked to a magnitude"
        assert any(o.get("magn_solo") is True for o in linked)

    def test_sessions_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        assert "sessions" not in data

    def test_magnitudes_absent_by_default(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates").get_json()
        assert "magnitudes" not in data
        assert "magnitude_details" not in data

    def test_no_db_returns_503(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/rates")
        assert r.status_code == 503


class TestRatesFilters:
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
        assert all(o["lim_magn"] >= 6.0 for o in data["observations"])
        assert len(data["observations"]) == 1

    def test_invalid_sl_min_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?sl_min=abc")
        assert r.status_code == 400
        assert "error" in r.get_json()


class TestRatesIncludes:
    def test_include_sessions(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?include=sessions").get_json()
        assert "sessions" in data
        assert len(data["sessions"]) > 0
        assert "id" in data["sessions"][0]

    def test_include_magnitudes_returns_full_observations(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?include=magnitudes").get_json()
        assert "magnitudes" in data
        assert "magnitude_details" not in data
        assert len(data["magnitudes"]) > 0
        # full MagnitudeObservation rows have mean and lim_magn, no per-class magn
        first = data["magnitudes"][0]
        assert "mean" in first
        assert "magn" not in first

    def test_include_magnitude_details_returns_frequencies(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/rates?include=magnitudes,magnitude_details"
        ).get_json()
        assert "magnitude_details" in data
        assert "magnitudes" in data
        assert len(data["magnitude_details"]) > 0
        # detail rows have magn and freq
        first = data["magnitude_details"][0]
        assert "magn" in first
        assert "freq" in first

    def test_include_magnitude_details_standalone(self, obs_client):
        # magnitude_details may be requested without magnitudes; each detail
        # row links back to a rate via Rate.magn_id.
        data = obs_client.get(f"{_BASE}/rates?include=magnitude_details").get_json()
        assert "magnitude_details" in data
        assert "magnitudes" not in data
        assert len(data["magnitude_details"]) > 0
        detail_ids = {d["id"] for d in data["magnitude_details"]}
        rate_magn_ids = {
            o["magn_id"] for o in data["observations"] if o.get("magn_id") is not None
        }
        assert detail_ids.issubset(rate_magn_ids)

    def test_include_combined(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/rates?include=sessions,magnitudes,magnitude_details"
        ).get_json()
        assert "sessions" in data
        assert "magnitudes" in data
        assert "magnitude_details" in data

    def test_unknown_include_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?include=evil")
        assert r.status_code == 400
        assert "error" in r.get_json()


class TestRatesPagination:
    def test_x_total_count_present_by_default(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates")
        assert r.status_code == 200
        assert r.headers.get("X-Total-Count") == "2"

    def test_limit_zero_returns_empty_observations(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?limit=0")
        assert r.status_code == 200
        data = r.get_json()
        assert data["observations"] == []
        assert r.headers.get("X-Total-Count") == "2"

    def test_limit_one_returns_one_row(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?limit=1")
        assert r.status_code == 200
        assert len(r.get_json()["observations"]) == 1
        assert r.headers.get("X-Total-Count") == "2"

    def test_offset_skips_rows(self, obs_client):
        full = obs_client.get(f"{_BASE}/rates").get_json()["observations"]
        offset = obs_client.get(f"{_BASE}/rates?offset=1").get_json()["observations"]
        assert [o["id"] for o in offset] == [o["id"] for o in full[1:]]

    def test_filter_combined_with_limit(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?shower=PER&limit=1")
        data = r.get_json()
        assert all(o["shower"] == "PER" for o in data["observations"])
        assert r.headers.get("X-Total-Count") == "1"


class TestRatesSortAndFields:
    def test_order_by_period_desc(self, obs_client):
        data = obs_client.get(
            f"{_BASE}/rates?order_by=period_start&order=desc"
        ).get_json()
        showers = [o["shower"] for o in data["observations"]]
        assert showers == ["GEM", "PER"]

    def test_invalid_order_by_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?order_by=evil")
        assert r.status_code == 400

    def test_fields_restricts_response(self, obs_client):
        data = obs_client.get(f"{_BASE}/rates?fields=id,shower").get_json()
        for obs in data["observations"]:
            assert set(obs.keys()) == {"id", "shower"}

    def test_unknown_field_returns_400(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates?fields=id,evil")
        assert r.status_code == 400


class TestRateSingle:
    def test_returns_200(self, obs_client):
        r = obs_client.get(f"{_BASE}/rates/1")
        assert r.status_code == 200
        assert r.get_json()["id"] == 1

    def test_unknown_returns_404(self, obs_client):
        assert obs_client.get(f"{_BASE}/rates/999").status_code == 404

    def test_no_db_returns_503(self, no_db_client):
        assert no_db_client.get(f"{_BASE}/rates/1").status_code == 503
