from dataclasses import dataclass, field


def _rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


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
    :param include_sessions: If ``True``, include a ``sessions`` key in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` key with the
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
    :param include_sessions: If ``True``, include a ``sessions`` key in the result.
    :param include_magnitudes: If ``True``, include a ``magnitudes`` key with the
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


def _add_shower_condition(showers, alias, conditions, params):
    if not showers:
        return
    normal = [s for s in showers if s != 'SPO']
    include_sporadic = 'SPO' in showers
    parts = []
    if normal:
        phs = ', '.join(f'%(sh_{i})s' for i in range(len(normal)))
        parts.append(f'{alias}.shower IN ({phs})')
        for i, s in enumerate(normal):
            params[f'sh_{i}'] = s
    if include_sporadic:
        parts.append(f'{alias}.shower IS NULL')
    if parts:
        conditions.append(f'({" OR ".join(parts)})')


def _build_rate_conditions(f: RateFilter):
    conditions = []
    params = {}

    _add_shower_condition(f.showers, 'r', conditions, params)

    if f.period_start:
        conditions.append('r.period_start >= %(period_start)s')
        params['period_start'] = f.period_start

    if f.period_end:
        conditions.append('r.period_end <= %(period_end)s')
        params['period_end'] = f.period_end

    for key, col, op, val in [
        ('sl_min',       'r.sl_start', '>=', f.sl_min),
        ('sl_max',       'r.sl_end',   '<=', f.sl_max),
        ('lim_magn_min', 'r.lim_mag',  '>=', f.lim_magn_min),
        ('lim_magn_max', 'r.lim_mag',  '<=', f.lim_magn_max),
        ('sun_alt_max',  'r.sun_alt',  '<=', f.sun_alt_max),
        ('moon_alt_max', 'r.moon_alt', '<=', f.moon_alt_max),
    ]:
        if val is not None:
            conditions.append(f'{col} {op} %({key})s')
            params[key] = val

    if f.session_ids:
        phs = ', '.join(f'%(sess_{i})s' for i in range(len(f.session_ids)))
        conditions.append(f'r.session_id IN ({phs})')
        for i, sid in enumerate(f.session_ids):
            params[f'sess_{i}'] = sid

    if f.rate_ids:
        phs = ', '.join(f'%(rate_{i})s' for i in range(len(f.rate_ids)))
        conditions.append(f'r.id IN ({phs})')
        for i, rid in enumerate(f.rate_ids):
            params[f'rate_{i}'] = rid

    return conditions, params


def _build_magnitude_conditions(f: MagnitudeFilter):
    conditions = []
    params = {}

    _add_shower_condition(f.showers, 'm', conditions, params)

    if f.period_start:
        conditions.append('m.period_start >= %(period_start)s')
        params['period_start'] = f.period_start

    if f.period_end:
        conditions.append('m.period_end <= %(period_end)s')
        params['period_end'] = f.period_end

    for key, col, op, val in [
        ('sl_min',       'm.sl_start', '>=', f.sl_min),
        ('sl_max',       'm.sl_end',   '<=', f.sl_max),
        ('lim_magn_min', 'm.lim_mag',  '>=', f.lim_magn_min),
        ('lim_magn_max', 'm.lim_mag',  '<=', f.lim_magn_max),
    ]:
        if val is not None:
            conditions.append(f'{col} {op} %({key})s')
            params[key] = val

    if f.session_ids:
        phs = ', '.join(f'%(sess_{i})s' for i in range(len(f.session_ids)))
        conditions.append(f'm.session_id IN ({phs})')
        for i, sid in enumerate(f.session_ids):
            params[f'sess_{i}'] = sid

    if f.magn_ids:
        phs = ', '.join(f'%(magn_{i})s' for i in range(len(f.magn_ids)))
        conditions.append(f'm.id IN ({phs})')
        for i, mid in enumerate(f.magn_ids):
            params[f'magn_{i}'] = mid

    return conditions, params


def _fetch_sessions(db_conn, session_ids):
    phs = ', '.join(f'%(sid_{i})s' for i in range(len(session_ids)))
    params = {f'sid_{i}': sid for i, sid in enumerate(session_ids)}
    stmt = f"""
        SELECT id, longitude, latitude, elevation, country, city,
               observer_id, observer_name
        FROM obs_session
        WHERE id IN ({phs})
    """
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt(stmt), params)
    return _rows_to_dicts(cur)


def _fetch_magnitude_details(db_conn, magn_ids):
    phs = ', '.join(f'%(mid_{i})s' for i in range(len(magn_ids)))
    params = {f'mid_{i}': mid for i, mid in enumerate(magn_ids)}
    stmt = f"""
        SELECT id, magn, freq
        FROM magnitude_detail
        WHERE id IN ({phs})
        ORDER BY id, magn DESC
    """
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt(stmt), params)
    return _rows_to_dicts(cur)


def query_showers(db_conn) -> list[dict]:
    """Return all meteor showers from the database.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :return: List of shower dicts with keys ``iau_code``, ``name``, ``start_month``,
        ``start_day``, ``end_month``, ``end_day``, ``peak_month``, ``peak_day``,
        ``ra``, ``dec``, ``v``, ``r``, ``zhr``.
    """
    cur = db_conn.cursor()
    cur.execute("""
        SELECT
            iau_code, name, start_month, start_day, end_month, end_day,
            peak_month, peak_day, ra, "dec", v, r, zhr
        FROM shower
        ORDER BY iau_code
    """)
    return _rows_to_dicts(cur)


def query_rates(db_conn, f: RateFilter) -> dict:
    """Query rate observations with optional filters.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param f: A :class:`RateFilter` specifying filter criteria and includes.
    :return: Dict with an ``observations`` key. If ``f.include_sessions`` is
        ``True``, a ``sessions`` key is added. If ``f.include_details`` is
        ``True``, a ``magnitudes`` key is added.
    """
    conditions, params = _build_rate_conditions(f)
    select = """
        SELECT
            r.id, r.shower, r.period_start, r.period_end, r.sl_start, r.sl_end,
            r.session_id, r.freq, r.lim_mag, r.t_eff, r.f, r.sidereal_time,
            r.sun_alt, r.sun_az, r.moon_alt, r.moon_az, r.moon_illum,
            r.field_alt, r.field_az, r.rad_alt, r.rad_az, rm.magn_id
        FROM rate r
        LEFT JOIN rate_magnitude rm ON r.id = rm.rate_id
    """
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt(f'{select} {where}'), params)
    observations = _rows_to_dicts(cur)

    result = {'observations': observations}

    if f.include_sessions:
        session_ids = list({r['session_id'] for r in observations if r['session_id'] is not None})
        result['sessions'] = _fetch_sessions(db_conn, session_ids) if session_ids else []

    if f.include_magnitudes:
        magn_ids = list({r['magn_id'] for r in observations if r['magn_id'] is not None})
        result['magnitudes'] = _fetch_magnitude_details(db_conn, magn_ids) if magn_ids else []

    return result


def query_magnitudes(db_conn, f: MagnitudeFilter) -> dict:
    """Query magnitude observations with optional filters.

    :param db_conn: An open database connection implementing DB-API 2.0.
    :param f: A :class:`MagnitudeFilter` specifying filter criteria and includes.
    :return: Dict with an ``observations`` key. If ``f.include_sessions`` is
        ``True``, a ``sessions`` key is added. If ``f.include_details`` is
        ``True``, a ``magnitudes`` key is added.
    """
    conditions, params = _build_magnitude_conditions(f)
    select = """
        SELECT
            m.id, m.shower, m.period_start, m.period_end, m.sl_start, m.sl_end,
            m.session_id, m.freq, m.mean, m.lim_mag
        FROM magnitude m
    """
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    cur = db_conn.cursor()
    cur.execute(db_conn.convert_stmt(f'{select} {where}'), params)
    observations = _rows_to_dicts(cur)

    result = {'observations': observations}

    if f.include_sessions:
        session_ids = list({r['session_id'] for r in observations if r['session_id'] is not None})
        result['sessions'] = _fetch_sessions(db_conn, session_ids) if session_ids else []

    if f.include_magnitudes:
        magn_ids = list({r['id'] for r in observations if r['id'] is not None})
        result['magnitudes'] = _fetch_magnitude_details(db_conn, magn_ids) if magn_ids else []

    return result
