import datetime
from dataclasses import dataclass, field

from imo_vmdb.db import DBAdapter

RATE_ORDER_FIELDS = frozenset(
    {"id", "period_start", "period_end", "sl_start", "lim_mag"}
)
MAGNITUDE_ORDER_FIELDS = frozenset(
    {"id", "period_start", "period_end", "sl_start", "lim_mag"}
)
SESSION_ORDER_FIELDS = frozenset({"id", "country", "observer_id"})


def _validate_order(order: str | None) -> str:
    if order is None:
        return "ASC"
    o = order.lower()
    if o not in ("asc", "desc"):
        raise ValueError(f"Invalid order: {order!r} (expected 'asc' or 'desc')")
    return o.upper()


def _validate_order_by(value: str | None, allowed: frozenset[str], default: str) -> str:
    if value is None:
        return default
    if value not in allowed:
        raise ValueError(f"Invalid order_by: {value!r} (allowed: {sorted(allowed)})")
    return value


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Shower:
    """Single meteor shower from the reference catalogue.

    See :ref:`fields` for field descriptions.
    """

    iau_code: str
    name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int
    peak_month: int | None
    peak_day: int | None
    ra: float | None
    dec: float | None
    v: float | None
    r: float | None
    zhr: float | None


@dataclass
class Session:
    """Observation session linked to rate or magnitude observations.

    See :ref:`fields` for field descriptions.
    """

    id: int
    longitude: float
    latitude: float
    elevation: float
    country: str
    city: str
    observer_id: int | None
    observer_name: str | None


@dataclass
class MagnitudeDetail:
    """Per-class frequency entry for a magnitude observation.

    See :ref:`fields` for field descriptions.
    """

    id: int
    magn: int
    freq: float


@dataclass
class Rate:
    """Single normalised rate observation returned by :meth:`RateService.query`.

    See :ref:`fields` for field descriptions.

    ``magn_id`` links to the associated :class:`Magnitude` observation via
    the ``rate_magnitude`` join table, or is ``None`` when no matching
    magnitude observation exists.
    """

    id: int
    shower: str | None
    period_start: str
    period_end: str
    sl_start: float
    sl_end: float
    session_id: int
    freq: int
    lim_mag: float
    t_eff: float
    f: float
    sidereal_time: float
    sun_alt: float
    sun_az: float
    moon_alt: float
    moon_az: float
    moon_illum: float
    field_alt: float | None
    field_az: float | None
    rad_alt: float | None
    rad_az: float | None
    magn_id: int | None


@dataclass
class Magnitude:
    """Single normalised magnitude observation returned by :meth:`MagnitudeService.query`.

    See :ref:`fields` for field descriptions.
    """

    id: int
    shower: str | None
    period_start: str
    period_end: str
    sl_start: float
    sl_end: float
    session_id: int
    freq: int
    mean: float
    lim_mag: float | None


@dataclass
class Radiant:
    """Radiant position of a meteor shower at a given calendar day."""

    shower: str
    month: int
    day: int
    ra: float
    dec: float


@dataclass
class Rates:
    """Return value of :meth:`RateService.query`.

    Always contains an ``observations`` list of :class:`Rate` instances.
    ``sessions`` (list of :class:`Session`) is only set when
    :attr:`RateFilter.include_sessions` is ``True``.
    ``magnitudes`` (list of :class:`MagnitudeDetail`) is only set when
    :attr:`RateFilter.include_magnitudes` is ``True``.
    ``total`` is the unpaginated row count and is only set when
    :attr:`RateFilter.with_total` is ``True`` (or when ``limit``/``offset``
    are used).
    """

    observations: list[Rate]
    sessions: list[Session] | None = None
    magnitudes: list[MagnitudeDetail] | None = None
    total: int | None = None


@dataclass
class Magnitudes:
    """Return value of :meth:`MagnitudeService.query`.

    Always contains an ``observations`` list of :class:`Magnitude` instances.
    ``sessions`` (list of :class:`Session`) is only set when
    :attr:`MagnitudeFilter.include_sessions` is ``True``.
    ``magnitudes`` (list of :class:`MagnitudeDetail`) is only set when
    :attr:`MagnitudeFilter.include_magnitudes` is ``True``.
    ``total`` is the unpaginated row count and is only set when
    :attr:`MagnitudeFilter.with_total` is ``True`` (or when ``limit``/``offset``
    are used).
    """

    observations: list[Magnitude]
    sessions: list[Session] | None = None
    magnitudes: list[MagnitudeDetail] | None = None
    total: int | None = None


@dataclass
class Sessions:
    """Return value of :meth:`SessionService.query`."""

    observations: list[Session]
    total: int | None = None


@dataclass
class StatsMeta:
    """Database scope summary returned by :meth:`StatsService.meta`."""

    sessions: int
    rates: int
    magnitudes: int
    period_start: str | None
    period_end: str | None


@dataclass
class ShowerStat:
    """Per-shower aggregate counts.  ``shower`` is ``None`` for sporadics."""

    shower: str | None
    rates: int
    magnitudes: int


@dataclass
class CountryStat:
    """Per-country aggregate counts."""

    country: str
    sessions: int
    rates: int
    magnitudes: int


@dataclass
class YearStat:
    """Per-year aggregate counts."""

    year: int
    rates: int
    magnitudes: int


# ---------------------------------------------------------------------------
# Filter dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RateFilter:
    """Filter criteria for rate observation queries.

    :param showers: IAU shower codes to include; use ``'SPO'`` for sporadics.
    :param period_start: Include only observations starting on or after this date (``YYYY-MM-DD``).
    :param period_end: Include only observations ending on or before this date (``YYYY-MM-DD``).
    :param sl_min: Minimum solar longitude (start of period).
    :param sl_max: Maximum solar longitude (end of period).
    :param lim_magn_min: Minimum limiting magnitude.
    :param lim_magn_max: Maximum limiting magnitude.
    :param sun_alt_max: Maximum sun altitude in degrees.
    :param moon_alt_max: Maximum moon altitude in degrees.
    :param session_ids: Restrict to specific session IDs.
    :param rate_ids: Restrict to specific rate record IDs.
    :param include_sessions: If ``True``, include a ``sessions`` list in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` list with the
        per-class magnitude-distribution detail rows (from ``magnitude_detail``)
        linked to each rate observation.
    """

    showers: list[str] = field(default_factory=list)
    period_start: str | None = None
    period_end: str | None = None
    sl_min: float | None = None
    sl_max: float | None = None
    lim_magn_min: float | None = None
    lim_magn_max: float | None = None
    sun_alt_max: float | None = None
    moon_alt_max: float | None = None
    session_ids: list[int] = field(default_factory=list)
    rate_ids: list[int] = field(default_factory=list)
    include_sessions: bool = False
    include_magnitudes: bool = False
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    order: str | None = None
    with_total: bool = False


@dataclass
class MagnitudeFilter:
    """Filter criteria for magnitude observation queries.

    :param showers: IAU shower codes to include; use ``'SPO'`` for sporadics.
    :param period_start: Include only observations starting on or after this date (``YYYY-MM-DD``).
    :param period_end: Include only observations ending on or before this date (``YYYY-MM-DD``).
    :param sl_min: Minimum solar longitude (start of period).
    :param sl_max: Maximum solar longitude (end of period).
    :param lim_magn_min: Minimum limiting magnitude.
    :param lim_magn_max: Maximum limiting magnitude.
    :param session_ids: Restrict to specific session IDs.
    :param magn_ids: Restrict to specific magnitude record IDs.
    :param include_sessions: If ``True``, include a ``sessions`` list in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` list with the
        per-class magnitude-distribution detail rows (from ``magnitude_detail``)
        for each magnitude observation.
    """

    showers: list[str] = field(default_factory=list)
    period_start: str | None = None
    period_end: str | None = None
    sl_min: float | None = None
    sl_max: float | None = None
    lim_magn_min: float | None = None
    lim_magn_max: float | None = None
    session_ids: list[int] = field(default_factory=list)
    magn_ids: list[int] = field(default_factory=list)
    include_sessions: bool = False
    include_magnitudes: bool = False
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    order: str | None = None
    with_total: bool = False


@dataclass
class SessionFilter:
    """Filter criteria for session queries.

    :param observer_ids: Restrict to specific observer IDs.
    :param period_start: Include only sessions with at least one rate or
        magnitude observation starting on or after this date.
    :param period_end: Include only sessions with at least one rate or
        magnitude observation ending on or before this date.
    :param limit: Maximum number of sessions to return.
    :param offset: Number of leading sessions to skip.
    :param order_by: Sort column (whitelist: ``id``, ``country``, ``observer_id``).
    :param order: ``"asc"`` or ``"desc"``.
    :param with_total: If ``True``, populate ``Sessions.total``.
    """

    observer_ids: list[int] = field(default_factory=list)
    period_start: str | None = None
    period_end: str | None = None
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    order: str | None = None
    with_total: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row, strict=False)) for row in cursor.fetchall()]


def _add_shower_condition(showers, alias, conditions, params):
    if not showers:
        return
    normal = [s for s in showers if s != "SPO"]
    include_sporadic = "SPO" in showers
    parts = []
    if normal:
        phs = ", ".join(f"%(sh_{i})s" for i in range(len(normal)))
        parts.append(f"{alias}.shower IN ({phs})")
        for i, s in enumerate(normal):
            params[f"sh_{i}"] = s
    if include_sporadic:
        parts.append(f"{alias}.shower IS NULL")
    if parts:
        conditions.append(f"({' OR '.join(parts)})")


def _build_rate_conditions(f: RateFilter):
    conditions = []
    params = {}

    _add_shower_condition(f.showers, "r", conditions, params)

    if f.period_start:
        conditions.append("r.period_start >= %(period_start)s")
        params["period_start"] = f.period_start

    if f.period_end:
        conditions.append("r.period_end <= %(period_end)s")
        params["period_end"] = f.period_end

    for key, col, op, val in [
        ("sl_min", "r.sl_start", ">=", f.sl_min),
        ("sl_max", "r.sl_end", "<=", f.sl_max),
        ("lim_magn_min", "r.lim_mag", ">=", f.lim_magn_min),
        ("lim_magn_max", "r.lim_mag", "<=", f.lim_magn_max),
        ("sun_alt_max", "r.sun_alt", "<=", f.sun_alt_max),
        ("moon_alt_max", "r.moon_alt", "<=", f.moon_alt_max),
    ]:
        if val is not None:
            conditions.append(f"{col} {op} %({key})s")
            params[key] = val

    if f.session_ids:
        phs = ", ".join(f"%(sess_{i})s" for i in range(len(f.session_ids)))
        conditions.append(f"r.session_id IN ({phs})")
        for i, sid in enumerate(f.session_ids):
            params[f"sess_{i}"] = sid

    if f.rate_ids:
        phs = ", ".join(f"%(rate_{i})s" for i in range(len(f.rate_ids)))
        conditions.append(f"r.id IN ({phs})")
        for i, rid in enumerate(f.rate_ids):
            params[f"rate_{i}"] = rid

    return conditions, params


def _build_magnitude_conditions(f: MagnitudeFilter):
    conditions = []
    params = {}

    _add_shower_condition(f.showers, "m", conditions, params)

    if f.period_start:
        conditions.append("m.period_start >= %(period_start)s")
        params["period_start"] = f.period_start

    if f.period_end:
        conditions.append("m.period_end <= %(period_end)s")
        params["period_end"] = f.period_end

    for key, col, op, val in [
        ("sl_min", "m.sl_start", ">=", f.sl_min),
        ("sl_max", "m.sl_end", "<=", f.sl_max),
        ("lim_magn_min", "m.lim_mag", ">=", f.lim_magn_min),
        ("lim_magn_max", "m.lim_mag", "<=", f.lim_magn_max),
    ]:
        if val is not None:
            conditions.append(f"{col} {op} %({key})s")
            params[key] = val

    if f.session_ids:
        phs = ", ".join(f"%(sess_{i})s" for i in range(len(f.session_ids)))
        conditions.append(f"m.session_id IN ({phs})")
        for i, sid in enumerate(f.session_ids):
            params[f"sess_{i}"] = sid

    if f.magn_ids:
        phs = ", ".join(f"%(magn_{i})s" for i in range(len(f.magn_ids)))
        conditions.append(f"m.id IN ({phs})")
        for i, mid in enumerate(f.magn_ids):
            params[f"magn_{i}"] = mid

    return conditions, params


def _build_session_conditions(f: SessionFilter):
    conditions: list[str] = []
    params: dict = {}

    if f.observer_ids:
        phs = ", ".join(f"%(obs_{i})s" for i in range(len(f.observer_ids)))
        conditions.append(f"s.observer_id IN ({phs})")
        for i, oid in enumerate(f.observer_ids):
            params[f"obs_{i}"] = oid

    if f.period_start or f.period_end:
        period_conds = []
        period_params = {}
        if f.period_start:
            period_conds.append("x.period_start >= %(s_period_start)s")
            period_params["s_period_start"] = f.period_start
        if f.period_end:
            period_conds.append("x.period_end <= %(s_period_end)s")
            period_params["s_period_end"] = f.period_end
        cond = " AND ".join(period_conds)
        conditions.append(
            "(EXISTS (SELECT 1 FROM rate x WHERE x.session_id = s.id AND "
            + cond
            + ") OR EXISTS (SELECT 1 FROM magnitude x WHERE x.session_id = s.id AND "
            + cond
            + "))"
        )
        params.update(period_params)

    return conditions, params


def _pagination_clause(limit: int | None, offset: int | None) -> str:
    parts = []
    if limit is not None:
        if limit < 0:
            raise ValueError("limit must be >= 0")
        parts.append(f"LIMIT {int(limit)}")
    if offset is not None:
        if offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is None:
            # MySQL requires a numeric LIMIT before OFFSET; use max int64
            # as a portable "unlimited" sentinel that works on SQLite, PG and MySQL.
            parts.append("LIMIT 9223372036854775807")
        parts.append(f"OFFSET {int(offset)}")
    return " ".join(parts)


def _fetch_sessions(db_conn, session_ids) -> list[Session]:
    phs = ", ".join(f"%(sid_{i})s" for i in range(len(session_ids)))
    params = {f"sid_{i}": sid for i, sid in enumerate(session_ids)}
    stmt = f"""
        SELECT id, longitude, latitude, elevation, country, city,
               observer_id, observer_name
        FROM obs_session
        WHERE id IN ({phs})
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), params)
    return [Session(**d) for d in _rows_to_dicts(cur)]


def _fetch_magnitude_details(db_conn, magn_ids) -> list[MagnitudeDetail]:
    phs = ", ".join(f"%(mid_{i})s" for i in range(len(magn_ids)))
    params = {f"mid_{i}": mid for i, mid in enumerate(magn_ids)}
    stmt = f"""
        SELECT id, magn, freq
        FROM magnitude_detail
        WHERE id IN ({phs})
        ORDER BY id, magn DESC
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), params)
    return [MagnitudeDetail(**d) for d in _rows_to_dicts(cur)]


def _shower_is_active(s: Shower, month: int, day: int) -> bool:
    start = (s.start_month, s.start_day)
    end = (s.end_month, s.end_day)
    md = (month, day)
    if start <= end:
        return start <= md <= end
    # Year-wrapping shower: active if md >= start OR md <= end.
    return md >= start or md <= end


# ---------------------------------------------------------------------------
# Service classes
# ---------------------------------------------------------------------------


class RateService:
    """Service for rate observation queries.

    :param db_conn: An open :class:`~imo_vmdb.db.DBAdapter` connection.
    """

    def __init__(self, db_conn: DBAdapter) -> None:
        self._db = db_conn

    def query(self, f: RateFilter) -> Rates:
        """Return rate observations matching *f*.

        :param f: A :class:`RateFilter` specifying filter criteria and includes.
        :return: A :class:`Rates` instance.  ``sessions`` and ``magnitudes`` are
            only set when the corresponding flags on *f* are ``True``.  ``total``
            is set when ``with_total`` is ``True`` or when pagination is in use.
        """
        conditions, params = _build_rate_conditions(f)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        order_col = _validate_order_by(f.order_by, RATE_ORDER_FIELDS, "id")
        order_dir = _validate_order(f.order)
        order_clause = f"ORDER BY r.{order_col} {order_dir}"

        paginated = f.limit is not None or f.offset is not None
        pag_clause = _pagination_clause(f.limit, f.offset)

        select = """
            SELECT
                r.id, r.shower, r.period_start, r.period_end, r.sl_start, r.sl_end,
                r.session_id, r.freq, r.lim_mag, r.t_eff, r.f, r.sidereal_time,
                r.sun_alt, r.sun_az, r.moon_alt, r.moon_az, r.moon_illum,
                r.field_alt, r.field_az, r.rad_alt, r.rad_az, rm.magn_id
            FROM rate r
            LEFT JOIN rate_magnitude rm ON r.id = rm.rate_id
        """
        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(f"{select} {where} {order_clause} {pag_clause}"),
            params,
        )
        observations = [Rate(**d) for d in _rows_to_dicts(cur)]

        result = Rates(observations=observations)

        if paginated or f.with_total:
            cur.execute(
                self._db._convert_stmt(f"SELECT COUNT(*) FROM rate r {where}"),
                params,
            )
            result.total = int(cur.fetchone()[0])

        if f.include_sessions:
            session_ids = list(
                {r.session_id for r in observations if r.session_id is not None}
            )
            result.sessions = (
                _fetch_sessions(self._db, session_ids) if session_ids else []
            )

        if f.include_magnitudes:
            magn_ids = list({r.magn_id for r in observations if r.magn_id is not None})
            result.magnitudes = (
                _fetch_magnitude_details(self._db, magn_ids) if magn_ids else []
            )

        return result

    def by_id(self, rate_id: int) -> Rate | None:
        """Return a single rate observation by ID, or ``None`` if not found."""
        result = self.query(RateFilter(rate_ids=[rate_id]))
        return result.observations[0] if result.observations else None


class MagnitudeService:
    """Service for magnitude observation queries.

    :param db_conn: An open :class:`~imo_vmdb.db.DBAdapter` connection.
    """

    def __init__(self, db_conn: DBAdapter) -> None:
        self._db = db_conn

    def query(self, f: MagnitudeFilter) -> Magnitudes:
        """Return magnitude observations matching *f*.

        :param f: A :class:`MagnitudeFilter` specifying filter criteria and includes.
        :return: A :class:`Magnitudes` instance.  ``sessions`` and ``magnitudes``
            are only set when the corresponding flags on *f* are ``True``.  ``total``
            is set when ``with_total`` is ``True`` or when pagination is in use.
        """
        conditions, params = _build_magnitude_conditions(f)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        order_col = _validate_order_by(f.order_by, MAGNITUDE_ORDER_FIELDS, "id")
        order_dir = _validate_order(f.order)
        order_clause = f"ORDER BY m.{order_col} {order_dir}"

        paginated = f.limit is not None or f.offset is not None
        pag_clause = _pagination_clause(f.limit, f.offset)

        select = """
            SELECT
                m.id, m.shower, m.period_start, m.period_end, m.sl_start, m.sl_end,
                m.session_id, m.freq, m.mean, m.lim_mag
            FROM magnitude m
        """
        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(f"{select} {where} {order_clause} {pag_clause}"),
            params,
        )
        observations = [Magnitude(**d) for d in _rows_to_dicts(cur)]

        result = Magnitudes(observations=observations)

        if paginated or f.with_total:
            cur.execute(
                self._db._convert_stmt(f"SELECT COUNT(*) FROM magnitude m {where}"),
                params,
            )
            result.total = int(cur.fetchone()[0])

        if f.include_sessions:
            session_ids = list(
                {r.session_id for r in observations if r.session_id is not None}
            )
            result.sessions = (
                _fetch_sessions(self._db, session_ids) if session_ids else []
            )

        if f.include_magnitudes:
            magn_ids = list({r.id for r in observations if r.id is not None})
            result.magnitudes = (
                _fetch_magnitude_details(self._db, magn_ids) if magn_ids else []
            )

        return result

    def by_id(self, magn_id: int) -> Magnitude | None:
        """Return a single magnitude observation by ID, or ``None`` if not found."""
        result = self.query(MagnitudeFilter(magn_ids=[magn_id]))
        return result.observations[0] if result.observations else None


class SessionService:
    """Service for observation session queries.

    :param db_conn: An open :class:`~imo_vmdb.db.DBAdapter` connection.
    """

    def __init__(self, db_conn: DBAdapter) -> None:
        self._db = db_conn

    def query(self, f: SessionFilter) -> Sessions:
        """Return sessions matching *f*."""
        conditions, params = _build_session_conditions(f)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        order_col = _validate_order_by(f.order_by, SESSION_ORDER_FIELDS, "id")
        order_dir = _validate_order(f.order)
        order_clause = f"ORDER BY s.{order_col} {order_dir}"

        paginated = f.limit is not None or f.offset is not None
        pag_clause = _pagination_clause(f.limit, f.offset)

        select = """
            SELECT s.id, s.longitude, s.latitude, s.elevation, s.country, s.city,
                   s.observer_id, s.observer_name
            FROM obs_session s
        """
        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(f"{select} {where} {order_clause} {pag_clause}"),
            params,
        )
        observations = [Session(**d) for d in _rows_to_dicts(cur)]
        result = Sessions(observations=observations)

        if paginated or f.with_total:
            cur.execute(
                self._db._convert_stmt(f"SELECT COUNT(*) FROM obs_session s {where}"),
                params,
            )
            result.total = int(cur.fetchone()[0])

        return result

    def by_id(self, session_id: int) -> Session | None:
        """Return a single session by ID, or ``None`` if not found."""
        sessions = _fetch_sessions(self._db, [session_id])
        return sessions[0] if sessions else None


class ShowerService:
    """Service for meteor shower reference data and radiants.

    :param db_conn: An open :class:`~imo_vmdb.db.DBAdapter` connection.
    """

    def __init__(self, db_conn: DBAdapter) -> None:
        self._db = db_conn

    def query(self) -> list[Shower]:
        """Return all meteor showers from the catalogue, ordered by IAU code."""
        cur = self._db.cursor()
        cur.execute("""
            SELECT
                iau_code, name, start_month, start_day, end_month, end_day,
                peak_month, peak_day, ra, "dec", v, r, zhr
            FROM shower
            ORDER BY iau_code
        """)
        return [Shower(**d) for d in _rows_to_dicts(cur)]

    def by_code(self, iau_code: str) -> Shower | None:
        """Return the shower with the given IAU code, or ``None`` if unknown."""
        cur = self._db.cursor()
        stmt = """
            SELECT iau_code, name, start_month, start_day, end_month, end_day,
                   peak_month, peak_day, ra, "dec", v, r, zhr
            FROM shower
            WHERE iau_code = %(code)s
        """
        cur.execute(self._db._convert_stmt(stmt), {"code": iau_code})
        rows = _rows_to_dicts(cur)
        return Shower(**rows[0]) if rows else None

    def active(self, on_date: datetime.date) -> list[Shower]:
        """Return all showers whose activity period covers *on_date*.

        Handles year-wrapping showers (e.g. start in December, end in January)
        by treating the period as inclusive on both ends.

        :param on_date: Calendar date to test against each shower's
            ``start_*`` / ``end_*`` fields.  Year is ignored.
        :return: List of matching :class:`Shower` instances.
        """
        m, d = on_date.month, on_date.day
        return [s for s in self.query() if _shower_is_active(s, m, d)]

    def radiants(self, iau_code: str) -> list[Radiant]:
        """Return all radiant entries for *iau_code*, ordered by ``(month, day)``."""
        cur = self._db.cursor()
        stmt = """
            SELECT shower, "month" AS month, "day" AS day, ra, "dec" AS dec
            FROM radiant
            WHERE shower = %(code)s
            ORDER BY "month", "day"
        """
        cur.execute(self._db._convert_stmt(stmt), {"code": iau_code})
        return [Radiant(**d) for d in _rows_to_dicts(cur)]


class StatsService:
    """Aggregate statistics over the observation database.

    All ``by_*`` methods accept an optional ``period_start``/``period_end``
    filter (ISO date strings) that restricts the rate and magnitude tables
    before aggregation.  Sessions are not period-filtered for ``meta`` and
    ``by_country`` to keep the semantics simple ("how many sessions are
    in the database").

    :param db_conn: An open :class:`~imo_vmdb.db.DBAdapter` connection.
    """

    def __init__(self, db_conn: DBAdapter) -> None:
        self._db = db_conn

    def meta(self) -> StatsMeta:
        """Return overall counts and the covered date range."""
        cur = self._db.cursor()
        cur.execute("SELECT COUNT(*) FROM obs_session")
        sessions = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*), MIN(period_start), MAX(period_end) FROM rate")
        rates_cnt, r_min, r_max = cur.fetchone()
        cur.execute(
            "SELECT COUNT(*), MIN(period_start), MAX(period_end) FROM magnitude"
        )
        magn_cnt, m_min, m_max = cur.fetchone()

        starts = [x for x in (r_min, m_min) if x is not None]
        ends = [x for x in (r_max, m_max) if x is not None]
        return StatsMeta(
            sessions=sessions,
            rates=int(rates_cnt),
            magnitudes=int(magn_cnt),
            period_start=str(min(starts)) if starts else None,
            period_end=str(max(ends)) if ends else None,
        )

    def by_shower(
        self, period_start: str | None = None, period_end: str | None = None
    ) -> list[ShowerStat]:
        """Return per-shower counts of rates and magnitudes."""
        rates = self._group_count("rate", "shower", period_start, period_end)
        magns = self._group_count("magnitude", "shower", period_start, period_end)
        keys = set(rates) | set(magns)
        return sorted(
            (
                ShowerStat(
                    shower=k,
                    rates=rates.get(k, 0),
                    magnitudes=magns.get(k, 0),
                )
                for k in keys
            ),
            key=lambda x: (x.shower is None, x.shower or ""),
        )

    def by_country(
        self, period_start: str | None = None, period_end: str | None = None
    ) -> list[CountryStat]:
        """Return per-country counts of sessions, rates and magnitudes."""
        cur = self._db.cursor()
        cur.execute("SELECT country, COUNT(*) FROM obs_session GROUP BY country")
        sessions = {row[0]: int(row[1]) for row in cur.fetchall()}

        rates = self._group_count_join("rate", period_start, period_end)
        magns = self._group_count_join("magnitude", period_start, period_end)

        keys = set(sessions) | set(rates) | set(magns)
        return sorted(
            (
                CountryStat(
                    country=k,
                    sessions=sessions.get(k, 0),
                    rates=rates.get(k, 0),
                    magnitudes=magns.get(k, 0),
                )
                for k in keys
            ),
            key=lambda x: x.country,
        )

    def by_year(
        self, period_start: str | None = None, period_end: str | None = None
    ) -> list[YearStat]:
        """Return per-year counts of rates and magnitudes."""
        rates = self._group_count_year("rate", period_start, period_end)
        magns = self._group_count_year("magnitude", period_start, period_end)
        keys = set(rates) | set(magns)
        return sorted(
            (
                YearStat(
                    year=k,
                    rates=rates.get(k, 0),
                    magnitudes=magns.get(k, 0),
                )
                for k in keys
            ),
            key=lambda x: x.year,
        )

    # --- private helpers ---

    def _period_clause(
        self, period_start: str | None, period_end: str | None
    ) -> tuple[str, dict]:
        conds = []
        params: dict = {}
        if period_start:
            conds.append("period_start >= %(period_start)s")
            params["period_start"] = period_start
        if period_end:
            conds.append("period_end <= %(period_end)s")
            params["period_end"] = period_end
        return ("WHERE " + " AND ".join(conds)) if conds else "", params

    def _group_count(
        self,
        table: str,
        column: str,
        period_start: str | None,
        period_end: str | None,
    ) -> dict:
        where, params = self._period_clause(period_start, period_end)
        stmt = f"SELECT {column}, COUNT(*) FROM {table} {where} GROUP BY {column}"
        cur = self._db.cursor()
        cur.execute(self._db._convert_stmt(stmt), params)
        return {row[0]: int(row[1]) for row in cur.fetchall()}

    def _group_count_join(
        self,
        obs_table: str,
        period_start: str | None,
        period_end: str | None,
    ) -> dict:
        conds = []
        params: dict = {}
        if period_start:
            conds.append(f"{obs_table}.period_start >= %(period_start)s")
            params["period_start"] = period_start
        if period_end:
            conds.append(f"{obs_table}.period_end <= %(period_end)s")
            params["period_end"] = period_end
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        stmt = (
            f"SELECT s.country, COUNT(*) "
            f"FROM {obs_table} JOIN obs_session s ON {obs_table}.session_id = s.id "
            f"{where} GROUP BY s.country"
        )
        cur = self._db.cursor()
        cur.execute(self._db._convert_stmt(stmt), params)
        return {row[0]: int(row[1]) for row in cur.fetchall()}

    def _group_count_year(
        self,
        table: str,
        period_start: str | None,
        period_end: str | None,
    ) -> dict:
        where, params = self._period_clause(period_start, period_end)
        year_sql = self._db._year_expr("period_start")
        stmt = f"SELECT {year_sql} AS y, COUNT(*) FROM {table} {where} GROUP BY y"
        cur = self._db.cursor()
        cur.execute(self._db._convert_stmt(stmt), params)
        return {int(row[0]): int(row[1]) for row in cur.fetchall()}
