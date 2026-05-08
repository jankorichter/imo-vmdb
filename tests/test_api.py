"""Tests for the Python API (query_showers, query_rates, query_magnitudes)."""

from imo_vmdb import (
    Magnitude,
    MagnitudeDetail,
    MagnitudeFilter,
    Magnitudes,
    Rate,
    RateFilter,
    Rates,
    Session,
    Shower,
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
        for attr in (
            "iau_code",
            "name",
            "start_month",
            "start_day",
            "end_month",
            "end_day",
        ):
            assert hasattr(shower, attr)


class TestQueryRates:
    def test_returns_rates_with_observations(self, seeded_db):
        result = query_rates(seeded_db, RateFilter())
        assert isinstance(result, Rates)

    def test_include_sessions_sets_sessions(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_sessions=True))
        assert result.sessions is not None

    def test_include_magnitudes_sets_magnitudes(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(include_magnitudes=True))
        assert result.magnitudes is not None

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER"]))
        assert isinstance(result, Rates)

    def test_sporadic_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["SPO"]))
        assert isinstance(result, Rates)

    def test_multi_shower_filter_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(showers=["PER", "GEM"]))
        assert isinstance(result, Rates)

    def test_numeric_filters_do_not_error(self, seeded_db):
        result = query_rates(
            seeded_db, RateFilter(sl_min=130.0, sl_max=150.0, lim_magn_min=5.0)
        )
        assert isinstance(result, Rates)

    def test_period_filter_does_not_error(self, seeded_db):
        result = query_rates(
            seeded_db, RateFilter(period_start="2020-01-01", period_end="2020-12-31")
        )
        assert isinstance(result, Rates)

    def test_lim_magn_max_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(lim_magn_max=7.0))
        assert isinstance(result, Rates)

    def test_sun_alt_max_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(sun_alt_max=-5.0))
        assert isinstance(result, Rates)

    def test_moon_alt_max_does_not_error(self, seeded_db):
        result = query_rates(seeded_db, RateFilter(moon_alt_max=30.0))
        assert isinstance(result, Rates)

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["PER"]))
        showers = [r.shower for r in result.observations]
        assert showers == ["PER"]

    def test_shower_filter_excludes_others(self, observation_db):
        result = query_rates(observation_db, RateFilter(showers=["GEM"]))
        showers = [r.shower for r in result.observations]
        assert "PER" not in showers

    def test_sl_range_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(sl_min=139.0, sl_max=142.0))
        showers = [r.shower for r in result.observations]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_lim_magn_min_restricts_results(self, observation_db):
        result = query_rates(observation_db, RateFilter(lim_magn_min=6.0))
        lim_mags = [r.lim_mag for r in result.observations]
        assert all(m >= 6.0 for m in lim_mags)
        assert len(lim_mags) == 1

    def test_include_sessions_returns_session_content(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        assert len(result.sessions) > 0
        assert isinstance(result.sessions[0], Session)


class TestQueryMagnitudes:
    def test_returns_magnitudes_with_observations(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter())
        assert isinstance(result, Magnitudes)

    def test_include_sessions_sets_sessions(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_sessions=True))
        assert result.sessions is not None

    def test_include_magnitudes_sets_magnitudes(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(include_magnitudes=True))
        assert result.magnitudes is not None

    def test_shower_filter_does_not_error(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(showers=["PER"]))
        assert isinstance(result, Magnitudes)

    def test_period_filter_does_not_error(self, seeded_db):
        result = query_magnitudes(
            seeded_db,
            MagnitudeFilter(period_start="2020-01-01", period_end="2020-12-31"),
        )
        assert isinstance(result, Magnitudes)

    def test_lim_magn_max_does_not_error(self, seeded_db):
        result = query_magnitudes(seeded_db, MagnitudeFilter(lim_magn_max=7.0))
        assert isinstance(result, Magnitudes)

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = query_magnitudes(observation_db, MagnitudeFilter(showers=["PER"]))
        showers = [r.shower for r in result.observations]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, observation_db):
        result = query_magnitudes(
            observation_db, MagnitudeFilter(sl_min=139.0, sl_max=142.0)
        )
        showers = [r.shower for r in result.observations]
        assert "PER" in showers
        assert "GEM" not in showers


class TestShowerShape:
    def test_isinstance(self, seeded_db):
        showers = query_showers(seeded_db)
        assert len(showers) > 0
        assert all(isinstance(s, Shower) for s in showers)


class TestRateShape:
    def test_rate_isinstance(self, observation_db):
        result = query_rates(observation_db, RateFilter())
        assert len(result.observations) > 0
        assert all(isinstance(obs, Rate) for obs in result.observations)

    def test_session_isinstance(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        assert len(result.sessions) > 0
        assert all(isinstance(s, Session) for s in result.sessions)

    def test_magnitude_detail_isinstance(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_magnitudes=True))
        assert len(result.magnitudes) > 0
        assert all(isinstance(d, MagnitudeDetail) for d in result.magnitudes)


class TestMagnitudeShape:
    def test_magnitude_isinstance(self, observation_db):
        result = query_magnitudes(observation_db, MagnitudeFilter())
        assert len(result.observations) > 0
        assert all(isinstance(obs, Magnitude) for obs in result.observations)

    def test_session_isinstance(self, observation_db):
        result = query_magnitudes(
            observation_db, MagnitudeFilter(include_sessions=True)
        )
        assert len(result.sessions) > 0
        assert all(isinstance(s, Session) for s in result.sessions)

    def test_magnitude_detail_isinstance(self, observation_db):
        result = query_magnitudes(
            observation_db, MagnitudeFilter(include_magnitudes=True)
        )
        assert len(result.magnitudes) > 0
        assert all(isinstance(d, MagnitudeDetail) for d in result.magnitudes)


class TestSessionFields:
    def test_numeric_geo_fields_are_float(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        session = result.sessions[0]
        assert isinstance(session.longitude, float)
        assert isinstance(session.latitude, float)
        assert isinstance(session.elevation, float)

    def test_string_location_fields(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_sessions=True))
        session = result.sessions[0]
        assert isinstance(session.country, str)
        assert isinstance(session.city, str)


class TestRateFields:
    def _rate(self, observation_db):
        return query_rates(observation_db, RateFilter()).observations[0]

    def test_id_is_int(self, observation_db):
        assert isinstance(self._rate(observation_db).id, int)

    def test_shower_is_str(self, observation_db):
        assert isinstance(self._rate(observation_db).shower, str)

    def test_freq_is_int(self, observation_db):
        assert isinstance(self._rate(observation_db).freq, int)

    def test_float_fields(self, observation_db):
        rate = self._rate(observation_db)
        for field in ("lim_mag", "sl_start", "sl_end"):
            assert isinstance(getattr(rate, field), float), f"{field} should be float"

    def test_period_fields_are_str(self, observation_db):
        rate = self._rate(observation_db)
        assert isinstance(rate.period_start, str)
        assert isinstance(rate.period_end, str)


class TestMagnitudeFields:
    def _magn(self, observation_db):
        return query_magnitudes(observation_db, MagnitudeFilter()).observations[0]

    def test_id_is_int(self, observation_db):
        assert isinstance(self._magn(observation_db).id, int)

    def test_shower_is_str(self, observation_db):
        assert isinstance(self._magn(observation_db).shower, str)

    def test_freq_is_int(self, observation_db):
        assert isinstance(self._magn(observation_db).freq, int)

    def test_float_fields(self, observation_db):
        magn = self._magn(observation_db)
        for field in ("sl_start", "sl_end", "mean"):
            assert isinstance(getattr(magn, field), float), f"{field} should be float"


class TestMagnitudeDetailFields:
    def test_magn_is_int(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_magnitudes=True))
        detail = result.magnitudes[0]
        assert isinstance(detail.magn, int)

    def test_freq_is_float(self, observation_db):
        result = query_rates(observation_db, RateFilter(include_magnitudes=True))
        detail = result.magnitudes[0]
        assert isinstance(detail.freq, float)
