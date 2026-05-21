import json
import logging
from datetime import datetime

import pytest

from imo_vmdb import (
    DuplicateSessionError,
    MagnitudeImport,
    RateImport,
    SessionImport,
    SessionImporter,
)

_START = datetime(2025, 8, 12, 22, 0, 0)
_END = datetime(2025, 8, 12, 23, 0, 0)


def _make_session(sid=1, *, rates=(), magnitudes=()):
    return SessionImport(
        id=sid,
        latitude=52.0,
        longitude=13.4,
        country="DE",
        location_name="Berlin",
        observer_id=42,
        observer_name="Test Observer",
        elevation=50.0,
        rates=rates,
        magnitudes=magnitudes,
    )


def _make_rate(rid, session_id):
    return RateImport(
        id=rid,
        session_id=session_id,
        period_start=_START,
        period_end=_END,
        t_eff=1.0,
        f=1.0,
        lim_magn=6.2,
        method="C",
        freq=17,
        shower="PER",
        ra=48.0,
        dec=57.0,
        observer_id=42,
    )


def _make_magn(mid, session_id):
    return MagnitudeImport(
        id=mid,
        session_id=session_id,
        period_start=_START,
        period_end=_END,
        magn={0: 1, 1: 2, 2: 5, 3: 0, 4: 3},
        observer_id=42,
        shower="PER",
    )


def _fetch_session(db, sid):
    cur = db.cursor()
    cur.execute("SELECT * FROM imported_session WHERE id = ?", (sid,))
    return cur.fetchone()


def _fetch_rates(db, sid):
    cur = db.cursor()
    cur.execute("SELECT * FROM imported_rate WHERE session_id = ?", (sid,))
    return cur.fetchall()


def _fetch_magnitudes(db, sid):
    cur = db.cursor()
    cur.execute("SELECT * FROM imported_magnitude WHERE session_id = ?", (sid,))
    return cur.fetchall()


# ---------------------------------------------------------------------------


def test_upload_happy_path(seeded_db):
    """Session + 2 rates + 1 magnitude are persisted; magn blob drops zero values."""
    session = _make_session(
        1,
        rates=(_make_rate(10, 1), _make_rate(11, 1)),
        magnitudes=(_make_magn(20, 1),),
    )
    cur = seeded_db.cursor()
    SessionImporter(cur).upload(session)
    seeded_db.commit()

    assert _fetch_session(seeded_db, 1) is not None
    assert len(_fetch_rates(seeded_db, 1)) == 2
    rows = _fetch_magnitudes(seeded_db, 1)
    assert len(rows) == 1
    magn = json.loads(rows[0][-1])
    assert "3" not in magn
    assert magn["0"] == 1
    assert magn["4"] == 3


def test_upload_duplicate_raises(seeded_db):
    """Second upload with the same session_id raises before issuing any statement."""
    session = _make_session(1, rates=(_make_rate(10, 1),))
    cur = seeded_db.cursor()
    imp = SessionImporter(cur)
    imp.upload(session)
    seeded_db.commit()

    with pytest.raises(DuplicateSessionError):
        imp.upload(session)

    assert len(_fetch_rates(seeded_db, 1)) == 1


def test_upload_replace_existing(seeded_db):
    """replace=True replaces the old session and its children with new data."""
    old = _make_session(1, rates=(_make_rate(10, 1), _make_rate(11, 1)))
    cur = seeded_db.cursor()
    imp = SessionImporter(cur)
    imp.upload(old)
    seeded_db.commit()

    new = _make_session(1, rates=(_make_rate(99, 1),), magnitudes=(_make_magn(88, 1),))
    imp.upload(new, replace=True)
    seeded_db.commit()

    rates = _fetch_rates(seeded_db, 1)
    assert len(rates) == 1
    assert rates[0][0] == 99
    assert len(_fetch_magnitudes(seeded_db, 1)) == 1


def test_upload_replace_nonexistent(seeded_db):
    """replace=True on a missing session just inserts without raising."""
    session = _make_session(1, rates=(_make_rate(10, 1),))
    cur = seeded_db.cursor()
    SessionImporter(cur).upload(session, replace=True)
    seeded_db.commit()

    assert _fetch_session(seeded_db, 1) is not None
    assert len(_fetch_rates(seeded_db, 1)) == 1


def test_delete_existing(seeded_db):
    """delete() removes session and all children; other sessions are untouched."""
    s1 = _make_session(1, rates=(_make_rate(10, 1),), magnitudes=(_make_magn(20, 1),))
    s2 = _make_session(2, rates=(_make_rate(11, 2),))
    cur = seeded_db.cursor()
    imp = SessionImporter(cur)
    imp.upload(s1)
    imp.upload(s2)
    seeded_db.commit()

    assert imp.delete(1) is True
    seeded_db.commit()

    assert _fetch_session(seeded_db, 1) is None
    assert len(_fetch_rates(seeded_db, 1)) == 0
    assert len(_fetch_magnitudes(seeded_db, 1)) == 0
    assert _fetch_session(seeded_db, 2) is not None
    assert len(_fetch_rates(seeded_db, 2)) == 1


def test_delete_nonexistent(seeded_db):
    """delete() on a missing session returns False without touching the DB."""
    cur = seeded_db.cursor()
    assert SessionImporter(cur).delete(999) is False
    assert _fetch_session(seeded_db, 999) is None


def test_compose_multiple_operations(seeded_db):
    """Multiple upload/delete calls share one transaction committed together."""
    old = _make_session(99, rates=(_make_rate(90, 99),))
    cur = seeded_db.cursor()
    imp = SessionImporter(cur)
    imp.upload(old)
    seeded_db.commit()

    s1 = _make_session(1, rates=(_make_rate(10, 1),))
    s2 = _make_session(2, magnitudes=(_make_magn(20, 2),))
    imp.upload(s1)
    imp.upload(s2)
    imp.delete(99)
    seeded_db.commit()

    assert _fetch_session(seeded_db, 1) is not None
    assert _fetch_session(seeded_db, 2) is not None
    assert _fetch_session(seeded_db, 99) is None


def test_rollback_by_caller(seeded_db):
    """Without commit(), rollback() leaves the DB unchanged."""
    session = _make_session(1, rates=(_make_rate(10, 1),))
    cur = seeded_db.cursor()
    SessionImporter(cur).upload(session)
    seeded_db.rollback()

    assert _fetch_session(seeded_db, 1) is None


def test_error_mid_insert_rollback(seeded_db, monkeypatch):
    """Exception from _insert_rate propagates; caller rollback leaves no partial data."""
    call_count = [0]
    original = SessionImporter._insert_rate

    def failing_insert(self, r):
        call_count[0] += 1
        if call_count[0] >= 2:
            raise RuntimeError("Simulated error on second rate insert")
        original(self, r)

    monkeypatch.setattr(SessionImporter, "_insert_rate", failing_insert)

    session = _make_session(1, rates=(_make_rate(10, 1), _make_rate(11, 1)))
    cur = seeded_db.cursor()
    try:
        SessionImporter(cur).upload(session)
    except RuntimeError:
        seeded_db.rollback()

    assert _fetch_session(seeded_db, 1) is None
    assert len(_fetch_rates(seeded_db, 1)) == 0


def test_datatypes(seeded_db):
    """datetime, NULL shower, and NULL elevation round-trip correctly through SQLite."""
    session = SessionImport(
        id=5,
        latitude=-33.9,
        longitude=151.2,
        country="AU",
        location_name="Sydney",
        elevation=None,
        rates=(
            RateImport(
                id=50,
                session_id=5,
                period_start=_START,
                period_end=_END,
                t_eff=0.5,
                f=1.2,
                lim_magn=5.5,
                method="V",
                freq=3,
                shower=None,
            ),
        ),
        magnitudes=(
            MagnitudeImport(
                id=60,
                session_id=5,
                period_start=_START,
                period_end=_END,
                magn={2: 4},
                shower="GEM",
            ),
        ),
    )
    cur = seeded_db.cursor()
    SessionImporter(cur).upload(session)
    seeded_db.commit()

    # elevation is NULL (column index 5 in imported_session)
    row = _fetch_session(seeded_db, 5)
    assert row is not None
    assert row[5] is None

    rates = _fetch_rates(seeded_db, 5)
    assert len(rates) == 1
    # shower is NULL for sporadic (column index 3 in imported_rate)
    assert rates[0][3] is None
    # "start" comes back as datetime (column index 4 in imported_rate)
    assert isinstance(rates[0][4], datetime)
    assert rates[0][4] == _START

    magnitudes = _fetch_magnitudes(seeded_db, 5)
    assert len(magnitudes) == 1
    # shower (column index 3 in imported_magnitude)
    assert magnitudes[0][3] == "GEM"


def test_csv_regression(seeded_db):
    """Existing CSV-import tests still work after the db.py refactor."""
    from pathlib import Path

    from imo_vmdb import CSVImporter

    fixtures = Path(__file__).parent / "fixtures"
    importer = CSVImporter(seeded_db, logging.getLogger("test"))
    importer.run(
        [
            str(fixtures / "sessions.csv"),
            str(fixtures / "rates.csv"),
            str(fixtures / "magnitudes.csv"),
        ]
    )
    seeded_db.commit()
    assert not importer.has_errors
    assert importer.counter_write > 0
