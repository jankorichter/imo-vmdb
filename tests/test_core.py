import logging
import math
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import imo_vmdb
from imo_vmdb import CSVImporter
from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBAdapter
from imo_vmdb.model.sky import Ephemeris, Sky, Location

FIXTURES = Path(__file__).parent / 'fixtures'
logger = logging.getLogger('test')


class TestEphemeris:
    DAY = datetime(2024, 8, 12, 0, 0, 0)

    def test_sun_cartesian_has_float_components(self):
        e = Ephemeris(self.DAY)
        assert isinstance(e.sun.x, float)
        assert isinstance(e.sun.y, float)
        assert isinstance(e.sun.z, float)

    def test_moon_cartesian_has_float_components(self):
        e = Ephemeris(self.DAY)
        assert isinstance(e.moon.x, float)
        assert isinstance(e.moon.y, float)
        assert isinstance(e.moon.z, float)

    def test_sun_distance_roughly_one_au(self):
        e = Ephemeris(self.DAY)
        r = math.sqrt(e.sun.x ** 2 + e.sun.y ** 2 + e.sun.z ** 2)
        assert 0.98 < r < 1.02

    def test_sky_sun_altitude_returns_sphere(self):
        sky = Sky()
        t = datetime(2024, 8, 12, 22, 0, 0)
        loc = Location(lng=math.radians(13.4), lat=math.radians(52.5))
        result = sky.sun(t, loc)
        assert hasattr(result, 'lat') and hasattr(result, 'lng')

    def test_sky_moon_illumination_in_range(self):
        sky = Sky()
        t = datetime(2024, 8, 12, 22, 0, 0)
        illum = sky.moon_illumination(t)
        assert 0.0 <= illum <= 1.0


class TestInitdb:
    def test_returns_zero(self, fresh_db):
        result = imo_vmdb.initdb(fresh_db, logger)
        assert result == 0

    def test_creates_core_tables(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        fresh_db.commit()
        cur = fresh_db.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cur.fetchall()}
        for expected in ('obs_session', 'rate', 'magnitude', 'shower', 'radiant'):
            assert expected in tables

    def test_imports_reference_showers(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute('SELECT COUNT(*) FROM shower')
        assert cur.fetchone()[0] > 0

    def test_imports_reference_radiants(self, fresh_db):
        imo_vmdb.initdb(fresh_db, logger)
        cur = fresh_db.cursor()
        cur.execute('SELECT COUNT(*) FROM radiant')
        assert cur.fetchone()[0] > 0


class TestCleanup:
    def test_returns_zero(self, seeded_db):
        result = imo_vmdb.cleanup(seeded_db, logger)
        assert result == 0

    def test_clears_imported_tables(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()

        cur = seeded_db.cursor()
        for table in ('imported_session', 'imported_rate', 'imported_magnitude'):
            cur.execute(f'SELECT COUNT(*) FROM {table}')
            assert cur.fetchone()[0] == 0, f'{table} should be empty after cleanup'

    def test_preserves_reference_data(self, seeded_db):
        imo_vmdb.cleanup(seeded_db, logger)
        seeded_db.commit()
        cur = seeded_db.cursor()
        cur.execute('SELECT COUNT(*) FROM shower')
        assert cur.fetchone()[0] > 0


class TestCSVImporter:
    def test_import_sessions(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'sessions.csv')])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_rates(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'rates.csv')])
        assert not importer.has_errors
        assert importer.counter_write == 2

    def test_import_magnitudes(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(FIXTURES / 'magnitudes.csv')])
        assert not importer.has_errors
        assert importer.counter_write >= 1

    def test_nonexistent_file_sets_error(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run(['/tmp/no_such_file_xyz_abc.csv'])
        assert importer.has_errors

    def test_unknown_csv_format_sets_error(self, seeded_db, tmp_path):
        bad = tmp_path / 'bad.csv'
        bad.write_text('col_a;col_b\n1;2\n')
        importer = CSVImporter(seeded_db, logger)
        importer.run([str(bad)])
        assert importer.has_errors

    def test_do_delete_replaces_previous_data(self, seeded_db):
        importer1 = CSVImporter(seeded_db, logger)
        importer1.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        importer2 = CSVImporter(seeded_db, logger, do_delete=True)
        importer2.run([str(FIXTURES / 'sessions.csv')])
        seeded_db.commit()

        cur = seeded_db.cursor()
        cur.execute('SELECT COUNT(*) FROM imported_session')
        assert cur.fetchone()[0] == 2

    def test_multiple_files_in_one_run(self, seeded_db):
        importer = CSVImporter(seeded_db, logger)
        importer.run([
            str(FIXTURES / 'sessions.csv'),
            str(FIXTURES / 'rates.csv'),
        ])
        assert not importer.has_errors
        assert importer.counter_write == 4


class TestCheckPeriod:
    MAX = timedelta(days=0.49)  # ~11h46m, same as all callers

    def _make_parser(self, try_repair=True, is_permissive=False):
        return CsvParser(MagicMock(), logging.getLogger('test_check_period'),
                         try_repair=try_repair, is_permissive=is_permissive)

    def test_valid_period_returned_unchanged(self):
        p = self._make_parser()
        s = datetime(2018, 8, 11, 21, 15, 0)
        e = datetime(2018, 8, 11, 23, 0, 0)
        assert p._check_period(s, e, self.MAX, 1, 1) == (s, e)

    def test_period_too_long_raises(self):
        p = self._make_parser()
        s = datetime(2018, 8, 11, 0, 0, 0)
        e = datetime(2018, 8, 11, 23, 0, 0)
        with pytest.raises(ImportException):
            p._check_period(s, e, self.MAX, 1, 1)

    def test_equal_start_end_permissive_warns(self):
        p = self._make_parser(is_permissive=True)
        t = datetime(2018, 8, 11, 21, 0, 0)
        result = p._check_period(t, t, self.MAX, 1, 1)
        assert result == (t, t)

    def test_equal_start_end_strict_raises(self):
        p = self._make_parser(is_permissive=False)
        t = datetime(2018, 8, 11, 21, 0, 0)
        with pytest.raises(ImportException):
            p._check_period(t, t, self.MAX, 1, 1)

    def test_swap_used_when_only_valid_candidate(self):
        # 22:00 -> 20:00 same day: swap=2h (valid), add-1-day=22h (fails max)
        p = self._make_parser()
        s = datetime(2018, 8, 11, 22, 0, 0)
        e = datetime(2018, 8, 11, 20, 0, 0)
        rs, re = p._check_period(s, e, self.MAX, 1, 1)
        assert rs == e and re == s

    def test_add_one_day_used_for_near_midnight_crossing(self):
        # 23:50 -> 00:10 same day: swap gives 23h40m (fails max), add-1-day gives 20min
        p = self._make_parser()
        s = datetime(2018, 8, 11, 23, 50, 0)
        e = datetime(2018, 8, 11, 0, 10, 0)
        rs, re = p._check_period(s, e, self.MAX, 1, 1)
        assert rs == s
        assert re == datetime(2018, 8, 12, 0, 10, 0)

    def test_motivating_example_adds_one_day_to_end(self):
        # 21:15 -> 02:52 same day: swap gives 18h23m (fails max), add-1-day gives 5h37m
        p = self._make_parser()
        s = datetime(2018, 8, 11, 21, 15, 0)
        e = datetime(2018, 8, 11, 2, 52, 0)
        rs, re = p._check_period(s, e, self.MAX, 1, 1)
        assert rs == s
        assert re == datetime(2018, 8, 12, 2, 52, 0)

    def test_shortest_candidate_wins_when_multiple_valid(self):
        # Choose a case where swap is valid but shorter than add-1-day
        # 22:00 -> 21:00 same day: swap=1h, add-1-day=23h (fails max) → swap wins
        p = self._make_parser()
        s = datetime(2018, 8, 11, 22, 0, 0)
        e = datetime(2018, 8, 11, 21, 0, 0)
        rs, re = p._check_period(s, e, self.MAX, 1, 1)
        assert rs == e and re == s

    def test_no_valid_candidate_raises(self):
        # start is 2 days after end: no candidate fits within max_period_duration
        p = self._make_parser()
        s = datetime(2018, 8, 13, 0, 0, 0)
        e = datetime(2018, 8, 11, 0, 0, 0)
        with pytest.raises(ImportException):
            p._check_period(s, e, self.MAX, 1, 1)

    def test_try_repair_false_raises_immediately(self):
        p = self._make_parser(try_repair=False)
        s = datetime(2018, 8, 11, 23, 0, 0)
        e = datetime(2018, 8, 11, 1, 0, 0)
        with pytest.raises(ImportException):
            p._check_period(s, e, self.MAX, 1, 1)
