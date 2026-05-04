"""Tests for the restapi query functions (RateFilter, MagnitudeFilter, query_*)."""

from imo_vmdb.restapi import (
    MagnitudeFilter,
    RateFilter,
    query_magnitudes,
    query_rates,
    query_showers,
)


class TestQueryShowers:
    def test_returns_non_empty_list(self, seeded_db):
        result = query_showers(seeded_db)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_items_have_expected_fields(self, seeded_db):
        result = query_showers(seeded_db)
        shower = result[0]
        for field in (
            "iau_code",
            "name",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
        ):
            assert field in shower


class TestQueryRates:
    def test_returns_dict_with_observations(self, seeded_db):
        result = query_rates(seeded_db, RateFilter())
        assert "observations" in result
        assert isinstance(result["observations"], list)

    def test_include_sessions_adds_key(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_sessions=True))
        assert "sessions" in result

    def test_include_magnitudes_adds_key(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_magnitudes=True))
        assert "magnitudes" in result

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER"]))
        assert "observations" in result

    def test_sporadic_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["SPO"]))
        assert "observations" in result

    def test_multi_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER", "GEM"]))
        assert "observations" in result

    def test_numeric_filters_do_not_error(self, seeded_db):
        result = query_rates(
            seeded_db, RateFilter(sl_min=130.0, sl_max=150.0, lim_magn_min=5.0)
        )
        assert "observations" in result

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["PER"]))
        showers = [r["shower"] for r in result["observations"]]
        assert showers == ["PER"]

    def test_shower_filter_excludes_others(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["GEM"]))
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" not in showers

    def test_sl_range_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(sl_min=139.0, sl_max=142.0))
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_lim_magn_min_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(lim_magn_min=6.0))
        lim_mags = [r["lim_mag"] for r in result["observations"]]
        assert all(m >= 6.0 for m in lim_mags)
        assert len(lim_mags) == 1

    def test_include_sessions_returns_session_content(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        assert len(result["sessions"]) > 0
        assert "id" in result["sessions"][0]


class TestQueryMagnitudes:
    def test_returns_dict_with_observations(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter())
        assert "observations" in result
        assert isinstance(result["observations"], list)

    def test_include_sessions_adds_key(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_sessions=True))
        assert "sessions" in result

    def test_include_magnitudes_adds_key(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_magnitudes=True))
        assert "magnitudes" in result

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(showers=["PER"]))
        assert "observations" in result

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_magnitudes(observation_db, MagnitudeFilter(showers=["PER"]))
        showers = [r["shower"] for r in result["observations"]]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, observation_db):
        result = query_magnitudes(
            observation_db, MagnitudeFilter(sl_min=139.0, sl_max=142.0)
        )
        showers = [r["shower"] for r in result["observations"]]
        assert "PER" in showers
        assert "GEM" not in showers
