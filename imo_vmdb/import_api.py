import json
from dataclasses import dataclass
from datetime import datetime

from imo_vmdb.db import DBAdapter


class DuplicateSessionError(Exception):
    """Raised when an upload targets a session id that already exists."""


@dataclass(frozen=True)
class RateImport:
    """A single rate observation to be uploaded together with its parent session.

    Pure container.  The caller is responsible for providing sensible values.
    """

    id: int
    session_id: int
    period_start: datetime
    period_end: datetime
    t_eff: float
    f: float
    lim_magn: float
    method: str
    freq: int
    observer_id: int | None = None
    shower: str | None = None
    ra: float | None = None
    dec: float | None = None


@dataclass(frozen=True)
class MagnitudeImport:
    """A single magnitude observation to be uploaded together with its parent session.

    Pure container.  The caller is responsible for providing sensible values.
    """

    id: int
    session_id: int
    period_start: datetime
    period_end: datetime
    magn: dict[int, float]
    observer_id: int | None = None
    shower: str | None = None


@dataclass(frozen=True)
class SessionImport:
    """An observation session plus its rates and magnitudes, ready to upload.

    Pure container.  The caller is responsible for providing sensible values.
    """

    id: int
    latitude: float
    longitude: float
    country: str
    location_name: str
    observer_id: int | None = None
    observer_name: str | None = None
    elevation: float | None = None
    rates: tuple[RateImport, ...] = ()
    magnitudes: tuple[MagnitudeImport, ...] = ()


class SessionImporter:
    """Issues DB statements for :class:`SessionImport`-based operations.

    The caller owns both the connection (transaction) and the cursor.
    This class neither commits, rolls back, nor opens a cursor of its own —
    all statements are issued on the cursor passed at construction time.
    Combine multiple operations into one transaction by issuing them on the
    same cursor between a single ``db.commit()`` / ``db.rollback()`` pair.

    :param cur: An open DB-API 2.0 cursor.
    """

    def __init__(self, cur) -> None:
        self._cur = cur

    def upload(self, session: SessionImport, replace: bool = False) -> None:
        """Issue INSERT statements for *session* and its children.

        :param session: Session to persist.
        :param replace: When ``True`` and a session with the same id already
            exists, DELETE statements for that session and its rates and
            magnitudes are issued first.  When ``False`` (the default), a
            pre-existing session raises :exc:`DuplicateSessionError` before
            any statement is issued.
        :raises DuplicateSessionError: If ``session.id`` already exists and
            ``replace`` is ``False``.
        :raises ~imo_vmdb.DBException: On database error.
        """
        if self._session_exists(session.id):
            if not replace:
                raise DuplicateSessionError("Session %d already exists." % session.id)
            self._delete_session_rows(session.id)
        self._insert_session(session)
        for r in session.rates:
            self._insert_rate(r)
        for m in session.magnitudes:
            self._insert_magnitude(m)

    def delete(self, session_id: int) -> bool:
        """Issue DELETE statements for *session_id* and all its rates and magnitudes.

        :param session_id: ID of the session to remove.
        :return: ``True`` if the session existed (statements were issued),
            ``False`` if no row with that id exists (no statement issued).
        :raises ~imo_vmdb.DBException: On database error.
        """
        if not self._session_exists(session_id):
            return False
        self._delete_session_rows(session_id)
        return True

    # ----- private ----------------------------------------------------------

    def _exec(self, stmt: str, params: dict) -> None:
        self._cur.execute(DBAdapter._convert_stmt_for_cursor(stmt, self._cur), params)

    def _session_exists(self, session_id: int) -> bool:
        self._exec(
            "SELECT 1 FROM imported_session WHERE id = %(id)s",
            {"id": session_id},
        )
        return self._cur.fetchone() is not None

    def _delete_session_rows(self, session_id: int) -> None:
        for table, col in (
            ("imported_magnitude", "session_id"),
            ("imported_rate", "session_id"),
            ("imported_session", "id"),
        ):
            self._exec(
                f"DELETE FROM {table} WHERE {col} = %(id)s",
                {"id": session_id},
            )

    def _insert_session(self, s: SessionImport) -> None:
        self._exec(
            """
            INSERT INTO imported_session (
                id, observer_id, observer_name, latitude, longitude,
                elevation, location_name, country
            ) VALUES (
                %(id)s, %(observer_id)s, %(observer_name)s, %(latitude)s, %(longitude)s,
                %(elevation)s, %(location_name)s, %(country)s
            )
            """,
            {
                "id": s.id,
                "observer_id": s.observer_id,
                "observer_name": s.observer_name,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "elevation": s.elevation,
                "location_name": s.location_name,
                "country": s.country,
            },
        )

    def _insert_rate(self, r: RateImport) -> None:
        self._exec(
            """
            INSERT INTO imported_rate (
                id, observer_id, session_id, "start", "end",
                t_eff, f, lm, ra, dec, shower, method, "number"
            ) VALUES (
                %(id)s, %(observer_id)s, %(session_id)s, %(start)s, %(end)s,
                %(t_eff)s, %(f)s, %(lm)s, %(ra)s, %(dec)s, %(shower)s, %(method)s, %(number)s
            )
            """,
            {
                "id": r.id,
                "observer_id": r.observer_id,
                "session_id": r.session_id,
                "start": r.period_start,
                "end": r.period_end,
                "t_eff": r.t_eff,
                "f": r.f,
                "lm": r.lim_magn,
                "ra": r.ra,
                "dec": r.dec,
                "shower": r.shower,
                "method": r.method,
                "number": r.freq,
            },
        )

    def _insert_magnitude(self, m: MagnitudeImport) -> None:
        magn_blob = json.dumps({str(k): v for k, v in m.magn.items() if v > 0})
        self._exec(
            """
            INSERT INTO imported_magnitude (
                id, observer_id, session_id, shower, "start", "end", magn
            ) VALUES (
                %(id)s, %(observer_id)s, %(session_id)s, %(shower)s,
                %(start)s, %(end)s, %(magn)s
            )
            """,
            {
                "id": m.id,
                "observer_id": m.observer_id,
                "session_id": m.session_id,
                "shower": m.shower,
                "start": m.period_start,
                "end": m.period_end,
                "magn": magn_blob,
            },
        )
