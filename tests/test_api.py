"""Tests for the Python service classes (RateService, MagnitudeService,
SessionService, ShowerService, StatsService) and DBAdapter.ping()."""

import datetime

import pytest

from imo_vmdb import (
    CountryStat,
    DBException,
    Magnitude,
    MagnitudeDetail,
    MagnitudeFilter,
    Magnitudes,
    MagnitudeService,
    Radiant,
    Rate,
    RateFilter,
    Rates,
    RateService,
    Session,
    SessionFilter,
    Sessions,
    SessionService,
    Shower,
    ShowerService,
    ShowerStat,
    StatsMeta,
    StatsService,
    YearStat,
)


class TestShowerServiceQuery:
    def test_returns_non_empty_list(self, seeded_db):
        result = ShowerService(seeded_db).query()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_items_have_expected_fields(self, seeded_db):
        result = ShowerService(seeded_db).query()
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


class TestRateServiceQuery:
    def test_returns_rates_with_observations(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter())
        assert isinstance(result, Rates)

    def test_include_sessions_sets_sessions(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(include_sessions=True))
        assert result.sessions is not None

    def test_include_magnitudes_sets_magnitudes(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(include_magnitudes=True))
        assert result.magnitudes is not None

    def test_shower_filter_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(showers=["PER"]))
        assert isinstance(result, Rates)

    def test_sporadic_filter_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(showers=["SPO"]))
        assert isinstance(result, Rates)

    def test_multi_shower_filter_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(showers=["PER", "GEM"]))
        assert isinstance(result, Rates)

    def test_numeric_filters_do_not_error(self, seeded_db):
        result = RateService(seeded_db).query(
            RateFilter(sl_min=130.0, sl_max=150.0, lim_magn_min=5.0)
        )
        assert isinstance(result, Rates)

    def test_period_filter_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(
            RateFilter(period_start="2020-01-01", period_end="2020-12-31")
        )
        assert isinstance(result, Rates)

    def test_lim_magn_max_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(lim_magn_max=7.0))
        assert isinstance(result, Rates)

    def test_sun_alt_max_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(sun_alt_max=-5.0))
        assert isinstance(result, Rates)

    def test_moon_alt_max_does_not_error(self, seeded_db):
        result = RateService(seeded_db).query(RateFilter(moon_alt_max=30.0))
        assert isinstance(result, Rates)

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = RateService(observation_db).query(RateFilter(showers=["PER"]))
        showers = [r.shower for r in result.observations]
        assert showers == ["PER"]

    def test_shower_filter_excludes_others(self, observation_db):
        result = RateService(observation_db).query(RateFilter(showers=["GEM"]))
        showers = [r.shower for r in result.observations]
        assert "PER" not in showers

    def test_sl_range_restricts_results(self, observation_db):
        result = RateService(observation_db).query(
            RateFilter(sl_min=139.0, sl_max=142.0)
        )
        showers = [r.shower for r in result.observations]
        assert "PER" in showers
        assert "GEM" not in showers

    def test_lim_magn_min_restricts_results(self, observation_db):
        result = RateService(observation_db).query(RateFilter(lim_magn_min=6.0))
        lim_mags = [r.lim_mag for r in result.observations]
        assert all(m >= 6.0 for m in lim_mags)
        assert len(lim_mags) == 1

    def test_include_sessions_returns_session_content(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_sessions=True))
        assert len(result.sessions) > 0
        assert isinstance(result.sessions[0], Session)


class TestMagnitudeServiceQuery:
    def test_returns_magnitudes_with_observations(self, seeded_db):
        result = MagnitudeService(seeded_db).query(MagnitudeFilter())
        assert isinstance(result, Magnitudes)

    def test_include_sessions_sets_sessions(self, seeded_db):
        result = MagnitudeService(seeded_db).query(
            MagnitudeFilter(include_sessions=True)
        )
        assert result.sessions is not None

    def test_include_magnitudes_sets_magnitudes(self, seeded_db):
        result = MagnitudeService(seeded_db).query(
            MagnitudeFilter(include_magnitudes=True)
        )
        assert result.magnitudes is not None

    def test_shower_filter_does_not_error(self, seeded_db):
        result = MagnitudeService(seeded_db).query(MagnitudeFilter(showers=["PER"]))
        assert isinstance(result, Magnitudes)

    def test_period_filter_does_not_error(self, seeded_db):
        result = MagnitudeService(seeded_db).query(
            MagnitudeFilter(period_start="2020-01-01", period_end="2020-12-31"),
        )
        assert isinstance(result, Magnitudes)

    def test_lim_magn_max_does_not_error(self, seeded_db):
        result = MagnitudeService(seeded_db).query(MagnitudeFilter(lim_magn_max=7.0))
        assert isinstance(result, Magnitudes)

    def test_shower_filter_returns_only_matching(self, observation_db):
        result = MagnitudeService(observation_db).query(
            MagnitudeFilter(showers=["PER"])
        )
        showers = [r.shower for r in result.observations]
        assert showers == ["PER"]

    def test_sl_range_restricts_results(self, observation_db):
        result = MagnitudeService(observation_db).query(
            MagnitudeFilter(sl_min=139.0, sl_max=142.0)
        )
        showers = [r.shower for r in result.observations]
        assert "PER" in showers
        assert "GEM" not in showers


class TestShowerShape:
    def test_isinstance(self, seeded_db):
        showers = ShowerService(seeded_db).query()
        assert len(showers) > 0
        assert all(isinstance(s, Shower) for s in showers)


class TestRateShape:
    def test_rate_isinstance(self, observation_db):
        result = RateService(observation_db).query(RateFilter())
        assert len(result.observations) > 0
        assert all(isinstance(obs, Rate) for obs in result.observations)

    def test_session_isinstance(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_sessions=True))
        assert len(result.sessions) > 0
        assert all(isinstance(s, Session) for s in result.sessions)

    def test_magnitude_detail_isinstance(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_magnitudes=True))
        assert len(result.magnitudes) > 0
        assert all(isinstance(d, MagnitudeDetail) for d in result.magnitudes)


class TestMagnitudeShape:
    def test_magnitude_isinstance(self, observation_db):
        result = MagnitudeService(observation_db).query(MagnitudeFilter())
        assert len(result.observations) > 0
        assert all(isinstance(obs, Magnitude) for obs in result.observations)

    def test_session_isinstance(self, observation_db):
        result = MagnitudeService(observation_db).query(
            MagnitudeFilter(include_sessions=True)
        )
        assert len(result.sessions) > 0
        assert all(isinstance(s, Session) for s in result.sessions)

    def test_magnitude_detail_isinstance(self, observation_db):
        result = MagnitudeService(observation_db).query(
            MagnitudeFilter(include_magnitudes=True)
        )
        assert len(result.magnitudes) > 0
        assert all(isinstance(d, MagnitudeDetail) for d in result.magnitudes)


class TestSessionFields:
    def test_numeric_geo_fields_are_float(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_sessions=True))
        session = result.sessions[0]
        assert isinstance(session.longitude, float)
        assert isinstance(session.latitude, float)
        assert isinstance(session.elevation, float)

    def test_string_location_fields(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_sessions=True))
        session = result.sessions[0]
        assert isinstance(session.country, str)
        assert isinstance(session.city, str)


class TestRateFields:
    def _rate(self, observation_db):
        return RateService(observation_db).query(RateFilter()).observations[0]

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
        return MagnitudeService(observation_db).query(MagnitudeFilter()).observations[0]

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
        result = RateService(observation_db).query(RateFilter(include_magnitudes=True))
        detail = result.magnitudes[0]
        assert isinstance(detail.magn, int)

    def test_freq_is_float(self, observation_db):
        result = RateService(observation_db).query(RateFilter(include_magnitudes=True))
        detail = result.magnitudes[0]
        assert isinstance(detail.freq, float)


# ---------------------------------------------------------------------------
# Pagination / sorting / total on RateService and MagnitudeService
# ---------------------------------------------------------------------------


class TestRatesPagination:
    def test_total_set_when_with_total(self, observation_db):
        result = RateService(observation_db).query(RateFilter(with_total=True))
        assert result.total == 2

    def test_total_none_by_default(self, observation_db):
        result = RateService(observation_db).query(RateFilter())
        assert result.total is None

    def test_limit_zero_returns_count_only(self, observation_db):
        result = RateService(observation_db).query(RateFilter(limit=0))
        assert result.observations == []
        assert result.total == 2

    def test_limit_one_returns_one(self, observation_db):
        result = RateService(observation_db).query(RateFilter(limit=1))
        assert len(result.observations) == 1
        assert result.total == 2

    def test_offset_skips(self, observation_db):
        full = RateService(observation_db).query(RateFilter()).observations
        offset = RateService(observation_db).query(RateFilter(offset=1)).observations
        assert [r.id for r in offset] == [r.id for r in full[1:]]

    def test_order_by_period_desc(self, observation_db):
        result = RateService(observation_db).query(
            RateFilter(order_by="period_start", order="desc")
        )
        # observation_db has 2023-08 (PER) and 2023-12 (GEM); desc → GEM first.
        assert [r.shower for r in result.observations] == ["GEM", "PER"]

    def test_invalid_order_by_raises(self, observation_db):
        with pytest.raises(ValueError):
            RateService(observation_db).query(RateFilter(order_by="malicious"))

    def test_invalid_order_raises(self, observation_db):
        with pytest.raises(ValueError):
            RateService(observation_db).query(RateFilter(order="sideways"))

    def test_negative_limit_raises(self, observation_db):
        with pytest.raises(ValueError):
            RateService(observation_db).query(RateFilter(limit=-1))


class TestMagnitudesPagination:
    def test_limit_zero_returns_count_only(self, observation_db):
        result = MagnitudeService(observation_db).query(MagnitudeFilter(limit=0))
        assert result.observations == []
        assert result.total == 2

    def test_with_total(self, observation_db):
        result = MagnitudeService(observation_db).query(
            MagnitudeFilter(with_total=True)
        )
        assert result.total == 2

    def test_total_none_by_default(self, observation_db):
        result = MagnitudeService(observation_db).query(MagnitudeFilter())
        assert result.total is None


# ---------------------------------------------------------------------------
# Single-resource lookups: RateService.by_id, MagnitudeService.by_id, SessionService
# ---------------------------------------------------------------------------


class TestRateServiceById:
    def test_returns_rate(self, observation_db):
        result = RateService(observation_db).by_id(1)
        assert isinstance(result, Rate)
        assert result.id == 1

    def test_unknown_returns_none(self, observation_db):
        assert RateService(observation_db).by_id(999) is None


class TestMagnitudeServiceById:
    def test_returns_magnitude(self, observation_db):
        result = MagnitudeService(observation_db).by_id(1)
        assert isinstance(result, Magnitude)
        assert result.id == 1

    def test_unknown_returns_none(self, observation_db):
        assert MagnitudeService(observation_db).by_id(999) is None


class TestSessionService:
    def test_by_id_returns_session(self, observation_db):
        result = SessionService(observation_db).by_id(1)
        assert isinstance(result, Session)
        assert result.id == 1

    def test_by_id_unknown_returns_none(self, observation_db):
        assert SessionService(observation_db).by_id(999) is None

    def test_query_returns_sessions(self, observation_db):
        result = SessionService(observation_db).query(SessionFilter())
        assert isinstance(result, Sessions)
        assert len(result.observations) == 1
        assert result.observations[0].id == 1

    def test_query_observer_id_filter(self, observation_db):
        # observation_db's session has no observer_id; filter on a non-existent one.
        result = SessionService(observation_db).query(SessionFilter(observer_ids=[42]))
        assert result.observations == []

    def test_query_period_filter_includes_matching(self, observation_db):
        result = SessionService(observation_db).query(
            SessionFilter(period_start="2023-01-01", period_end="2023-12-31")
        )
        assert len(result.observations) == 1

    def test_query_period_filter_excludes_outside(self, observation_db):
        result = SessionService(observation_db).query(
            SessionFilter(period_start="2030-01-01", period_end="2030-12-31")
        )
        assert result.observations == []

    def test_query_with_total(self, observation_db):
        result = SessionService(observation_db).query(SessionFilter(with_total=True))
        assert result.total == 1


# ---------------------------------------------------------------------------
# ShowerService
# ---------------------------------------------------------------------------


class TestShowerService:
    def test_query_returns_non_empty_list(self, seeded_db):
        result = ShowerService(seeded_db).query()
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(s, Shower) for s in result)

    def test_by_code_returns_shower(self, seeded_db):
        per = ShowerService(seeded_db).by_code("PER")
        assert isinstance(per, Shower)
        assert per.iau_code == "PER"

    def test_by_code_unknown_returns_none(self, seeded_db):
        assert ShowerService(seeded_db).by_code("ZZZ") is None

    def test_active_includes_in_period(self, seeded_db):
        # Perseids peak around mid-August.
        active = ShowerService(seeded_db).active(datetime.date(2024, 8, 12))
        codes = [s.iau_code for s in active]
        assert "PER" in codes

    def test_active_excludes_outside_period(self, seeded_db):
        # Pick a date unlikely to overlap with Perseids.
        active = ShowerService(seeded_db).active(datetime.date(2024, 5, 1))
        codes = [s.iau_code for s in active]
        assert "PER" not in codes

    def test_active_year_wrapping_shower(self, seeded_db):
        # Inject a synthetic year-wrapping shower (Dec 28 – Jan 5).
        cur = seeded_db.cursor()
        cur.execute(
            "INSERT INTO shower (id, iau_code, name, start_month, start_day, "
            'end_month, end_day, peak_month, peak_day, ra, "dec", v, r, zhr) '
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                9999,
                "TST",
                "Year-wrap test",
                12,
                28,
                1,
                5,
                1,
                3,
                0.0,
                0.0,
                40.0,
                2.5,
                50.0,
            ),
        )
        seeded_db.commit()

        # Both endpoints inside the wrap should be active.
        for d in (datetime.date(2024, 12, 31), datetime.date(2024, 1, 1)):
            codes = [s.iau_code for s in ShowerService(seeded_db).active(d)]
            assert "TST" in codes, f"TST should be active on {d}"

        # A date in the gap should not be active.
        codes = [
            s.iau_code
            for s in ShowerService(seeded_db).active(datetime.date(2024, 6, 1))
        ]
        assert "TST" not in codes

    def test_radiants_returns_sorted_entries(self, seeded_db):
        radiants = ShowerService(seeded_db).radiants("PER")
        assert len(radiants) > 0
        assert all(isinstance(r, Radiant) for r in radiants)
        keys = [(r.month, r.day) for r in radiants]
        assert keys == sorted(keys)

    def test_radiants_unknown_shower(self, seeded_db):
        assert ShowerService(seeded_db).radiants("ZZZ") == []


# ---------------------------------------------------------------------------
# StatsService
# ---------------------------------------------------------------------------


def _insert_extra_year_data(db_conn):
    """Add a 2024 rate + magnitude for a second observer/country."""
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO obs_session (id, longitude, latitude, elevation, country, city, "
        "observer_id, observer_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (2, 2.3, 48.8, 35.0, "FR", "Paris", 7, "Marie"),
    )
    cur.execute(
        "INSERT INTO rate (id, shower, period_start, period_end, sl_start, sl_end, "
        "session_id, freq, lim_mag, t_eff, f, sidereal_time, sun_alt, sun_az, "
        "moon_alt, moon_az, moon_illum) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            10,
            "PER",
            "2024-08-12 22:00",
            "2024-08-12 23:00",
            139.5,
            140.5,
            2,
            8,
            6.2,
            1.0,
            1.0,
            180.0,
            -20.0,
            270.0,
            -10.0,
            90.0,
            0.1,
        ),
    )
    cur.execute(
        "INSERT INTO magnitude (id, shower, period_start, period_end, sl_start, sl_end, "
        "session_id, freq, mean, lim_mag) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            10,
            "PER",
            "2024-08-12 22:00",
            "2024-08-12 23:00",
            139.5,
            140.5,
            2,
            40,
            3.1,
            6.2,
        ),
    )
    db_conn.commit()


class TestStatsService:
    def test_meta_counts(self, observation_db):
        meta = StatsService(observation_db).meta()
        assert isinstance(meta, StatsMeta)
        assert meta.sessions == 1
        assert meta.rates == 2
        assert meta.magnitudes == 2

    def test_meta_period(self, observation_db):
        meta = StatsService(observation_db).meta()
        assert meta.period_start.startswith("2023-08-12")
        assert meta.period_end.startswith("2023-12-14")

    def test_meta_empty_db(self, seeded_db):
        meta = StatsService(seeded_db).meta()
        assert meta.rates == 0
        assert meta.magnitudes == 0
        assert meta.period_start is None
        assert meta.period_end is None

    def test_by_shower(self, observation_db):
        result = StatsService(observation_db).by_shower()
        codes = {r.shower for r in result}
        assert codes == {"PER", "GEM"}
        assert all(isinstance(r, ShowerStat) for r in result)

    def test_by_shower_period_filter(self, observation_db):
        result = StatsService(observation_db).by_shower(
            period_start="2023-08-01", period_end="2023-09-30"
        )
        codes = {r.shower for r in result}
        assert codes == {"PER"}

    def test_by_country(self, observation_db):
        result = StatsService(observation_db).by_country()
        assert all(isinstance(r, CountryStat) for r in result)
        de = next(r for r in result if r.country == "DE")
        assert de.sessions == 1
        assert de.rates == 2
        assert de.magnitudes == 2

    def test_by_country_with_extra_country(self, observation_db):
        _insert_extra_year_data(observation_db)
        result = {r.country: r for r in StatsService(observation_db).by_country()}
        assert set(result) == {"DE", "FR"}
        assert result["FR"].rates == 1

    def test_by_year(self, observation_db):
        _insert_extra_year_data(observation_db)
        result = StatsService(observation_db).by_year()
        assert all(isinstance(r, YearStat) for r in result)
        years = {r.year: r for r in result}
        assert set(years) == {2023, 2024}
        assert years[2023].rates == 2
        assert years[2024].rates == 1

    def test_by_year_period_filter(self, observation_db):
        _insert_extra_year_data(observation_db)
        result = StatsService(observation_db).by_year(
            period_start="2024-01-01", period_end="2024-12-31"
        )
        assert {r.year for r in result} == {2024}


# ---------------------------------------------------------------------------
# DBAdapter.ping() — liveness check
# ---------------------------------------------------------------------------


class TestDBAdapterPing:
    def test_ping_succeeds_on_open_db(self, seeded_db):
        seeded_db.ping()  # should not raise

    def test_ping_raises_on_closed_db(self, seeded_db):
        seeded_db.close()
        with pytest.raises(DBException):
            seeded_db.ping()
