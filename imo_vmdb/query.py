import datetime
import json
from dataclasses import dataclass, field

from imo_vmdb.db import DBAdapter

RATE_ORDER_FIELDS = frozenset(
    {"id", "period_start", "period_end", "sl_start", "lim_magn"}
)
MAGNITUDE_ORDER_FIELDS = frozenset(
    {"id", "period_start", "period_end", "sl_start", "lim_magn"}
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
    location_name: str
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

    ``magn_id`` links to the associated :class:`Magnitude` observation, or
    is ``None`` when no matching magnitude observation exists.
    ``magn_solo`` is ``True`` when this rate is the only contributor to its
    linked magnitude (their periods match exactly), ``False`` when the
    magnitude observation aggregates this rate together with others over a
    longer period, and ``None`` when ``magn_id`` is ``None``.
    """

    id: int
    shower: str | None
    period_start: datetime.datetime
    period_end: datetime.datetime
    sl_start: float
    sl_end: float
    session_id: int
    freq: int
    lim_magn: float
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
    magn_solo: bool | None


@dataclass
class Magnitude:
    """Single normalised magnitude observation returned by :meth:`MagnitudeService.query`.

    See :ref:`fields` for field descriptions.
    """

    id: int
    shower: str | None
    period_start: datetime.datetime
    period_end: datetime.datetime
    sl_start: float
    sl_end: float
    session_id: int
    freq: int
    mean: float
    lim_magn: float | None


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
    """Return value of :meth:`RateService.query`."""

    observations: list[Rate]
    sessions: list[Session] | None = None
    magnitudes: list[Magnitude] | None = None
    magnitude_details: list[MagnitudeDetail] | None = None
    total: int | None = None


@dataclass
class Magnitudes:
    """Return value of :meth:`MagnitudeService.query`."""

    observations: list[Magnitude]
    sessions: list[Session] | None = None
    magnitude_details: list[MagnitudeDetail] | None = None
    total: int | None = None


@dataclass
class Sessions:
    """Return value of :meth:`SessionService.query`."""

    sessions: list[Session]
    rates: list[Rate] | None = None
    magnitudes: list[Magnitude] | None = None
    total: int | None = None


@dataclass
class StatsMeta:
    """Database scope summary returned by :meth:`StatsService.meta`.

    ``sessions``/``rates``/``magnitudes`` and ``*_meteors`` cover the
    normalized tables; the ``imported_*`` fields cover the raw imported
    tables that feed normalization.  ``*_meteors`` are the sum of the
    ``freq`` column on the rate/magnitude rows.  ``period_start`` /
    ``period_end`` is the union of ``rate_period_*`` and
    ``magnitude_period_*`` (kept for backward compatibility).
    """

    sessions: int
    rates: int
    magnitudes: int
    period_start: datetime.datetime | None
    period_end: datetime.datetime | None
    rate_meteors: int = 0
    magnitude_meteors: int = 0
    rate_period_start: datetime.datetime | None = None
    rate_period_end: datetime.datetime | None = None
    magnitude_period_start: datetime.datetime | None = None
    magnitude_period_end: datetime.datetime | None = None
    imported_sessions: int = 0
    imported_rates: int = 0
    imported_magnitudes: int = 0
    imported_rate_meteors: int = 0
    imported_magnitude_meteors: int = 0


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
    :param period_start: Include only observations starting at or after
        this :class:`datetime.datetime` (UTC).
    :param period_end: Include only observations ending at or before
        this :class:`datetime.datetime` (UTC).
    :param sl_min: Minimum solar longitude (start of period).
    :param sl_max: Maximum solar longitude (end of period).
    :param lim_magn_min: Minimum limiting magnitude.
    :param lim_magn_max: Maximum limiting magnitude.
    :param sun_alt_max: Maximum sun altitude in degrees.
    :param moon_alt_max: Maximum moon altitude in degrees.
    :param session_ids: Restrict to specific session IDs.
    :param rate_ids: Restrict to specific rate record IDs.
    :param include_sessions: If ``True``, include a ``sessions`` list in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` list with
        the full :class:`Magnitude` observations referenced by the returned
        rates via their ``magn_id``.
    :param include_magnitude_details: If ``True``, include a
        ``magnitude_details`` list with the per-magnitude-class
        frequencies (from ``magnitude_detail``) for the magnitude
        observations referenced by the returned rates.
    """

    showers: list[str] = field(default_factory=list)
    period_start: datetime.datetime | None = None
    period_end: datetime.datetime | None = None
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
    include_magnitude_details: bool = False
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    order: str | None = None
    with_total: bool = False


@dataclass
class MagnitudeFilter:
    """Filter criteria for magnitude observation queries.

    :param showers: IAU shower codes to include; use ``'SPO'`` for sporadics.
    :param period_start: Include only observations starting at or after
        this :class:`datetime.datetime` (UTC).
    :param period_end: Include only observations ending at or before
        this :class:`datetime.datetime` (UTC).
    :param sl_min: Minimum solar longitude (start of period).
    :param sl_max: Maximum solar longitude (end of period).
    :param lim_magn_min: Minimum limiting magnitude.
    :param lim_magn_max: Maximum limiting magnitude.
    :param session_ids: Restrict to specific session IDs.
    :param magn_ids: Restrict to specific magnitude record IDs.
    :param include_sessions: If ``True``, include a ``sessions`` list in the result.
    :param include_magnitude_details: If ``True``, include a
        ``magnitude_details`` list with the per-magnitude-class
        frequencies (from ``magnitude_detail``) for each magnitude
        observation.
    """

    showers: list[str] = field(default_factory=list)
    period_start: datetime.datetime | None = None
    period_end: datetime.datetime | None = None
    sl_min: float | None = None
    sl_max: float | None = None
    lim_magn_min: float | None = None
    lim_magn_max: float | None = None
    session_ids: list[int] = field(default_factory=list)
    magn_ids: list[int] = field(default_factory=list)
    include_sessions: bool = False
    include_magnitude_details: bool = False
    limit: int | None = None
    offset: int | None = None
    order_by: str | None = None
    order: str | None = None
    with_total: bool = False


@dataclass
class SessionFilter:
    """Filter criteria for session queries.

    The observation-level filters (``showers``, ``period_*``, ``sl_*``,
    ``lim_magn_*``) match sessions that have **at least one** rate or
    magnitude observation satisfying the criteria.  When an include is
    requested (``include_rates`` / ``include_magnitudes``), the returned
    observations are filtered by the same criteria, restricted to the
    session IDs in the result page.

    :param observer_ids: Restrict to specific observer IDs.
    :param showers: IAU shower codes to include; use ``'SPO'`` for sporadics.
    :param period_start: Include only sessions with at least one rate or
        magnitude observation starting at or after this
        :class:`datetime.datetime` (UTC).
    :param period_end: Include only sessions with at least one rate or
        magnitude observation ending at or before this
        :class:`datetime.datetime` (UTC).
    :param sl_min: Minimum solar longitude (start of period) across rate/magnitude.
    :param sl_max: Maximum solar longitude (end of period) across rate/magnitude.
    :param lim_magn_min: Minimum limiting magnitude across rate/magnitude.
    :param lim_magn_max: Maximum limiting magnitude across rate/magnitude.
    :param include_rates: If ``True``, include a ``rates`` list of full
        :class:`Rate` observations in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` list of
        full :class:`Magnitude` observations in the result.
    :param limit: Maximum number of sessions to return.
    :param offset: Number of leading sessions to skip.
    :param order_by: Sort column (whitelist: ``id``, ``country``, ``observer_id``).
    :param order: ``"asc"`` or ``"desc"``.
    :param with_total: If ``True``, populate ``Sessions.total``.
    """

    observer_ids: list[int] = field(default_factory=list)
    showers: list[str] = field(default_factory=list)
    period_start: datetime.datetime | None = None
    period_end: datetime.datetime | None = None
    sl_min: float | None = None
    sl_max: float | None = None
    lim_magn_min: float | None = None
    lim_magn_max: float | None = None
    include_rates: bool = False
    include_magnitudes: bool = False
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
        ("lim_magn_min", "r.lim_magn", ">=", f.lim_magn_min),
        ("lim_magn_max", "r.lim_magn", "<=", f.lim_magn_max),
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
        ("lim_magn_min", "m.lim_magn", ">=", f.lim_magn_min),
        ("lim_magn_max", "m.lim_magn", "<=", f.lim_magn_max),
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


def _observation_conditions(f: SessionFilter, alias: str, prefix: str):
    """Build the observation-level WHERE fragments shared by ``/sessions``
    filtering and ``include`` fetching.

    *alias* is the SQL alias of the rate or magnitude row in the surrounding
    query (e.g. ``"x"`` inside an EXISTS subquery, ``"r"`` or ``"m"`` in a
    direct SELECT).  *prefix* namespaces the placeholder names so the helper
    can be invoked multiple times within a single statement without
    collisions.
    """
    conditions: list[str] = []
    params: dict = {}

    if f.period_start:
        conditions.append(f"{alias}.period_start >= %({prefix}_period_start)s")
        params[f"{prefix}_period_start"] = f.period_start
    if f.period_end:
        conditions.append(f"{alias}.period_end <= %({prefix}_period_end)s")
        params[f"{prefix}_period_end"] = f.period_end
    if f.sl_min is not None:
        conditions.append(f"{alias}.sl_start >= %({prefix}_sl_min)s")
        params[f"{prefix}_sl_min"] = f.sl_min
    if f.sl_max is not None:
        conditions.append(f"{alias}.sl_end <= %({prefix}_sl_max)s")
        params[f"{prefix}_sl_max"] = f.sl_max
    if f.lim_magn_min is not None:
        conditions.append(f"{alias}.lim_magn >= %({prefix}_lim_magn_min)s")
        params[f"{prefix}_lim_magn_min"] = f.lim_magn_min
    if f.lim_magn_max is not None:
        conditions.append(f"{alias}.lim_magn <= %({prefix}_lim_magn_max)s")
        params[f"{prefix}_lim_magn_max"] = f.lim_magn_max

    if f.showers:
        normal = [s for s in f.showers if s != "SPO"]
        include_sporadic = "SPO" in f.showers
        parts = []
        if normal:
            phs = ", ".join(f"%({prefix}_sh_{i})s" for i in range(len(normal)))
            parts.append(f"{alias}.shower IN ({phs})")
            for i, s in enumerate(normal):
                params[f"{prefix}_sh_{i}"] = s
        if include_sporadic:
            parts.append(f"{alias}.shower IS NULL")
        if parts:
            conditions.append(f"({' OR '.join(parts)})")

    return conditions, params


def _has_observation_filter(f: SessionFilter) -> bool:
    return bool(
        f.period_start
        or f.period_end
        or f.sl_min is not None
        or f.sl_max is not None
        or f.lim_magn_min is not None
        or f.lim_magn_max is not None
        or f.showers
    )


def _build_session_conditions(f: SessionFilter):
    conditions: list[str] = []
    params: dict = {}

    if f.observer_ids:
        phs = ", ".join(f"%(obs_{i})s" for i in range(len(f.observer_ids)))
        conditions.append(f"s.observer_id IN ({phs})")
        for i, oid in enumerate(f.observer_ids):
            params[f"obs_{i}"] = oid

    if _has_observation_filter(f):
        obs_conds, obs_params = _observation_conditions(f, alias="x", prefix="sessobs")
        cond = " AND ".join(obs_conds)
        conditions.append(
            "(EXISTS (SELECT 1 FROM rate x WHERE x.session_id = s.id AND "
            + cond
            + ") OR EXISTS (SELECT 1 FROM magnitude x WHERE x.session_id = s.id AND "
            + cond
            + "))"
        )
        params.update(obs_params)

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


def _fetch_sessions(
    db_conn, page_cte_body: str, page_params: dict, fk_col: str
) -> list[Session]:
    """Fetch the sessions referenced by the page-CTE.

    *page_cte_body* is the inner SELECT that defines the ``page`` CTE
    (i.e. the same WHERE/ORDER BY/LIMIT/OFFSET as the main query that
    produced the result page).  *fk_col* names the column in the CTE
    projection that holds the session ID (``session_id`` for rate or
    magnitude pages).  ``IS NOT NULL`` guards the join in case the
    column is nullable in the source table — harmless when it isn't.
    """
    stmt = f"""
        WITH page AS ({page_cte_body})
        SELECT s.id, s.longitude, s.latitude, s.elevation, s.country,
               s.location_name, s.observer_id, s.observer_name
        FROM obs_session s
        WHERE s.id IN (SELECT {fk_col} FROM page WHERE {fk_col} IS NOT NULL)
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), page_params)
    return [Session(**d) for d in _rows_to_dicts(cur)]


_RATE_SELECT = """
    SELECT
        r.id, r.shower, r.period_start, r.period_end, r.sl_start, r.sl_end,
        r.session_id, r.freq, r.lim_magn, r.t_eff, r.f, r.sidereal_time,
        r.sun_alt, r.sun_az, r.moon_alt, r.moon_az, r.moon_illum,
        r.field_alt, r.field_az, r.rad_alt, r.rad_az, r.magn_id, r.magn_solo
    FROM rate r
"""


def _rate_from_row(d: dict) -> Rate:
    """Build a :class:`Rate` from a SELECT row, coercing booleans.

    SQLite stores booleans as 0/1 integers; coerce here so callers
    consistently see ``True``/``False``/``None`` regardless of backend.
    """
    if d.get("magn_solo") is not None:
        d = {**d, "magn_solo": bool(d["magn_solo"])}
    return Rate(**d)


_MAGNITUDE_SELECT = """
    SELECT
        m.id, m.shower, m.period_start, m.period_end, m.sl_start, m.sl_end,
        m.session_id, m.freq, m.mean, m.lim_magn
    FROM magnitude m
"""


def _fetch_session_rates(
    db_conn, f: SessionFilter, page_cte_body: str, page_params: dict
) -> list[Rate]:
    """Fetch rate observations for the sessions in the page-CTE, applying
    the same observation-level filters as the outer ``/sessions`` query."""
    conds, params = _observation_conditions(f, alias="r", prefix="rateobs")
    params.update(page_params)
    conds.append("r.session_id IN (SELECT id FROM page)")
    where = "WHERE " + " AND ".join(conds)
    stmt = f"""
        WITH page AS ({page_cte_body})
        {_RATE_SELECT} {where} ORDER BY r.id
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), params)
    return [_rate_from_row(d) for d in _rows_to_dicts(cur)]


def _fetch_session_magnitudes(
    db_conn, f: SessionFilter, page_cte_body: str, page_params: dict
) -> list[Magnitude]:
    """Fetch magnitude observations for the sessions in the page-CTE,
    applying the same observation-level filters as the outer ``/sessions``
    query."""
    conds, params = _observation_conditions(f, alias="m", prefix="magnobs")
    params.update(page_params)
    conds.append("m.session_id IN (SELECT id FROM page)")
    where = "WHERE " + " AND ".join(conds)
    stmt = f"""
        WITH page AS ({page_cte_body})
        {_MAGNITUDE_SELECT} {where} ORDER BY m.id
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), params)
    return [Magnitude(**d) for d in _rows_to_dicts(cur)]


def _fetch_magnitude_details(
    db_conn, page_cte_body: str, page_params: dict, fk_col: str
) -> list[MagnitudeDetail]:
    """Fetch per-class frequencies for the magnitudes referenced by the
    page-CTE.  *fk_col* is ``magn_id`` when paged over ``rate``, ``id``
    when paged over ``magnitude``."""
    stmt = f"""
        WITH page AS ({page_cte_body})
        SELECT id, magn, freq
        FROM magnitude_detail
        WHERE id IN (SELECT {fk_col} FROM page WHERE {fk_col} IS NOT NULL)
        ORDER BY id, magn DESC
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), page_params)
    return [MagnitudeDetail(**d) for d in _rows_to_dicts(cur)]


def _fetch_magnitudes(
    db_conn, page_cte_body: str, page_params: dict, fk_col: str
) -> list[Magnitude]:
    """Fetch full magnitude observations referenced by the page-CTE.

    *fk_col* is ``magn_id`` (when paged over ``rate``).
    """
    stmt = f"""
        WITH page AS ({page_cte_body})
        {_MAGNITUDE_SELECT}
        WHERE m.id IN (SELECT {fk_col} FROM page WHERE {fk_col} IS NOT NULL)
        ORDER BY m.id
    """
    cur = db_conn.cursor()
    cur.execute(db_conn._convert_stmt(stmt), page_params)
    return [Magnitude(**d) for d in _rows_to_dicts(cur)]


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
        :return: A :class:`Rates` instance.  ``sessions``, ``magnitudes`` and
            ``magnitude_details`` are only set when the corresponding flags on
            *f* are ``True``.  ``total`` is set when ``with_total`` is ``True``
            or when pagination is in use.
        """
        conditions, params = _build_rate_conditions(f)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        order_col = _validate_order_by(f.order_by, RATE_ORDER_FIELDS, "id")
        order_dir = _validate_order(f.order)
        order_clause = f"ORDER BY r.{order_col} {order_dir}"

        paginated = f.limit is not None or f.offset is not None
        pag_clause = _pagination_clause(f.limit, f.offset)

        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(
                f"{_RATE_SELECT} {where} {order_clause} {pag_clause}"
            ),
            params,
        )
        observations = [_rate_from_row(d) for d in _rows_to_dicts(cur)]

        result = Rates(observations=observations)

        if paginated or f.with_total:
            cur.execute(
                self._db._convert_stmt(f"SELECT COUNT(*) FROM rate r {where}"),
                params,
            )
            result.total = int(cur.fetchone()[0])

        if f.include_sessions or f.include_magnitudes or f.include_magnitude_details:
            if not observations:
                if f.include_sessions:
                    result.sessions = []
                if f.include_magnitudes:
                    result.magnitudes = []
                if f.include_magnitude_details:
                    result.magnitude_details = []
                return result

            # The page-CTE re-runs the same filter (and ORDER BY / LIMIT /
            # OFFSET when paginating) so the DB resolves the referenced
            # session and magnitude IDs itself — no Python ID-list shipped
            # back to the server.  Sort + pagination are omitted when not
            # paginating so the planner can skip the sort.
            page_clause = f"{order_clause} {pag_clause}" if paginated else ""
            page_cte_body = (
                f"SELECT r.id, r.session_id, r.magn_id "
                f"FROM rate r {where} {page_clause}"
            )

            if f.include_sessions:
                result.sessions = _fetch_sessions(
                    self._db, page_cte_body, params, fk_col="session_id"
                )
            if f.include_magnitudes:
                result.magnitudes = _fetch_magnitudes(
                    self._db, page_cte_body, params, fk_col="magn_id"
                )
            if f.include_magnitude_details:
                result.magnitude_details = _fetch_magnitude_details(
                    self._db, page_cte_body, params, fk_col="magn_id"
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
        :return: A :class:`Magnitudes` instance.  ``sessions`` and
            ``magnitude_details`` are only set when the corresponding flags on
            *f* are ``True``.  ``total`` is set when ``with_total`` is ``True``
            or when pagination is in use.
        """
        conditions, params = _build_magnitude_conditions(f)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        order_col = _validate_order_by(f.order_by, MAGNITUDE_ORDER_FIELDS, "id")
        order_dir = _validate_order(f.order)
        order_clause = f"ORDER BY m.{order_col} {order_dir}"

        paginated = f.limit is not None or f.offset is not None
        pag_clause = _pagination_clause(f.limit, f.offset)

        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(
                f"{_MAGNITUDE_SELECT} {where} {order_clause} {pag_clause}"
            ),
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

        if f.include_sessions or f.include_magnitude_details:
            if not observations:
                if f.include_sessions:
                    result.sessions = []
                if f.include_magnitude_details:
                    result.magnitude_details = []
                return result

            page_clause = f"{order_clause} {pag_clause}" if paginated else ""
            page_cte_body = (
                f"SELECT m.id, m.session_id FROM magnitude m {where} {page_clause}"
            )

            if f.include_sessions:
                result.sessions = _fetch_sessions(
                    self._db, page_cte_body, params, fk_col="session_id"
                )
            if f.include_magnitude_details:
                result.magnitude_details = _fetch_magnitude_details(
                    self._db, page_cte_body, params, fk_col="id"
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
            SELECT s.id, s.longitude, s.latitude, s.elevation, s.country, s.location_name,
                   s.observer_id, s.observer_name
            FROM obs_session s
        """
        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(f"{select} {where} {order_clause} {pag_clause}"),
            params,
        )
        sessions = [Session(**d) for d in _rows_to_dicts(cur)]
        result = Sessions(sessions=sessions)

        if paginated or f.with_total:
            cur.execute(
                self._db._convert_stmt(f"SELECT COUNT(*) FROM obs_session s {where}"),
                params,
            )
            result.total = int(cur.fetchone()[0])

        if f.include_rates or f.include_magnitudes:
            if not sessions:
                if f.include_rates:
                    result.rates = []
                if f.include_magnitudes:
                    result.magnitudes = []
                return result

            page_clause = f"{order_clause} {pag_clause}" if paginated else ""
            page_cte_body = f"SELECT s.id FROM obs_session s {where} {page_clause}"

            if f.include_rates:
                result.rates = _fetch_session_rates(self._db, f, page_cte_body, params)
            if f.include_magnitudes:
                result.magnitudes = _fetch_session_magnitudes(
                    self._db, f, page_cte_body, params
                )

        return result

    def by_id(self, session_id: int) -> Session | None:
        """Return a single session by ID, or ``None`` if not found."""
        cur = self._db.cursor()
        cur.execute(
            self._db._convert_stmt(
                """
                SELECT id, longitude, latitude, elevation, country, location_name,
                       observer_id, observer_name
                FROM obs_session
                WHERE id = %(id)s
                """
            ),
            {"id": session_id},
        )
        rows = _rows_to_dicts(cur)
        return Session(**rows[0]) if rows else None


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
        """Return overall counts and the covered date range.

        Tolerates missing tables: a database where ``initdb`` has not yet
        been run (or which is mid-rebuild) yields zeros and ``None``
        date bounds instead of raising, so the Web UI can poll the
        endpoint at any time without crashing.
        """
        cur = self._db.cursor()

        def _row(sql, default):
            try:
                cur.execute(sql)
                return cur.fetchone()
            except Exception:
                return default

        def _as_dt(v):
            # SQLite's `PARSE_DECLTYPES` only fires for columns whose
            # declared type the cursor reports.  `MIN(period_start)` /
            # `MAX(period_end)` strip that information and the value
            # arrives as a raw text string.  PostgreSQL and MySQL
            # drivers preserve it natively.  Normalize so callers
            # always see `datetime.datetime`.
            if isinstance(v, str):
                return datetime.datetime.fromisoformat(v)
            return v

        (sessions,) = _row("SELECT COUNT(*) FROM obs_session", (0,))
        rates_cnt, rate_meteors, r_min, r_max = _row(
            "SELECT COUNT(*), COALESCE(SUM(freq), 0), "
            "MIN(period_start), MAX(period_end) FROM rate",
            (0, 0, None, None),
        )
        r_min, r_max = _as_dt(r_min), _as_dt(r_max)
        magn_cnt, magn_meteors, m_min, m_max = _row(
            "SELECT COUNT(*), COALESCE(SUM(freq), 0), "
            "MIN(period_start), MAX(period_end) FROM magnitude",
            (0, 0, None, None),
        )
        m_min, m_max = _as_dt(m_min), _as_dt(m_max)
        (imported_sessions,) = _row("SELECT COUNT(*) FROM imported_session", (0,))
        # imported_rate uses `number` instead of `freq`.
        imp_rates_cnt, imp_rate_meteors = _row(
            'SELECT COUNT(*), COALESCE(SUM("number"), 0) FROM imported_rate',
            (0, 0),
        )
        # imported_magnitude.magn is a JSON object {class: count}; sum the
        # values in Python to get the total meteor count.
        (imp_magn_cnt,) = _row("SELECT COUNT(*) FROM imported_magnitude", (0,))
        try:
            cur.execute("SELECT magn FROM imported_magnitude")
            imp_magn_meteors = sum(
                sum(json.loads(row[0]).values()) for row in cur.fetchall()
            )
        except Exception:
            imp_magn_meteors = 0

        starts = [x for x in (r_min, m_min) if x is not None]
        ends = [x for x in (r_max, m_max) if x is not None]
        return StatsMeta(
            sessions=int(sessions),
            rates=int(rates_cnt),
            magnitudes=int(magn_cnt),
            period_start=min(starts) if starts else None,
            period_end=max(ends) if ends else None,
            rate_meteors=int(rate_meteors),
            magnitude_meteors=int(magn_meteors),
            rate_period_start=r_min,
            rate_period_end=r_max,
            magnitude_period_start=m_min,
            magnitude_period_end=m_max,
            imported_sessions=int(imported_sessions),
            imported_rates=int(imp_rates_cnt),
            imported_magnitudes=int(imp_magn_cnt),
            imported_rate_meteors=int(imp_rate_meteors),
            imported_magnitude_meteors=int(imp_magn_meteors),
        )

    def by_shower(
        self,
        period_start: datetime.datetime | None = None,
        period_end: datetime.datetime | None = None,
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
        self,
        period_start: datetime.datetime | None = None,
        period_end: datetime.datetime | None = None,
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
        self,
        period_start: datetime.datetime | None = None,
        period_end: datetime.datetime | None = None,
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
        self,
        period_start: datetime.datetime | None,
        period_end: datetime.datetime | None,
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
        period_start: datetime.datetime | None,
        period_end: datetime.datetime | None,
    ) -> dict:
        where, params = self._period_clause(period_start, period_end)
        stmt = f"SELECT {column}, COUNT(*) FROM {table} {where} GROUP BY {column}"
        cur = self._db.cursor()
        cur.execute(self._db._convert_stmt(stmt), params)
        return {row[0]: int(row[1]) for row in cur.fetchall()}

    def _group_count_join(
        self,
        obs_table: str,
        period_start: datetime.datetime | None,
        period_end: datetime.datetime | None,
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
        period_start: datetime.datetime | None,
        period_end: datetime.datetime | None,
    ) -> dict:
        where, params = self._period_clause(period_start, period_end)
        year_sql = self._db._year_expr("period_start")
        stmt = f"SELECT {year_sql} AS y, COUNT(*) FROM {table} {where} GROUP BY y"
        cur = self._db.cursor()
        cur.execute(self._db._convert_stmt(stmt), params)
        return {int(row[0]): int(row[1]) for row in cur.fetchall()}
