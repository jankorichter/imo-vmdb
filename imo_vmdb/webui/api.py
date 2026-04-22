import os

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from imo_vmdb.db import DBAdapter

api_bp = Blueprint('api', __name__)

_OPENAPI_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'docs', 'openapi.yaml')
)


def _rows_to_dicts(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def _get_db(config):
    return DBAdapter(dict(config['database']))


def _add_shower_condition(args, alias, conditions, params):
    showers = args.getlist('shower')
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


def _build_rate_conditions(args):
    conditions = []
    params = {}

    _add_shower_condition(args, 'r', conditions, params)

    period_start = args.get('period_start')
    if period_start:
        conditions.append('r.period_start >= %(period_start)s')
        params['period_start'] = period_start

    period_end = args.get('period_end')
    if period_end:
        conditions.append('r.period_end <= %(period_end)s')
        params['period_end'] = period_end

    try:
        for key, col, op in [
            ('sl_min',       'r.sl_start', '>='),
            ('sl_max',       'r.sl_end',   '<='),
            ('lim_magn_min', 'r.lim_mag',  '>='),
            ('lim_magn_max', 'r.lim_mag',  '<='),
            ('sun_alt_max',  'r.sun_alt',  '<='),
            ('moon_alt_max', 'r.moon_alt', '<='),
        ]:
            val = args.get(key)
            if val is not None:
                conditions.append(f'{col} {op} %({key})s')
                params[key] = float(val)

        session_ids = args.getlist('session_id')
        if session_ids:
            phs = ', '.join(f'%(sess_{i})s' for i in range(len(session_ids)))
            conditions.append(f'r.session_id IN ({phs})')
            for i, sid in enumerate(session_ids):
                params[f'sess_{i}'] = int(sid)

        rate_ids = args.getlist('rate_id')
        if rate_ids:
            phs = ', '.join(f'%(rate_{i})s' for i in range(len(rate_ids)))
            conditions.append(f'r.id IN ({phs})')
            for i, rid in enumerate(rate_ids):
                params[f'rate_{i}'] = int(rid)

    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid parameter value: {exc}')

    return conditions, params


def _build_magnitude_conditions(args):
    conditions = []
    params = {}

    _add_shower_condition(args, 'm', conditions, params)

    period_start = args.get('period_start')
    if period_start:
        conditions.append('m.period_start >= %(period_start)s')
        params['period_start'] = period_start

    period_end = args.get('period_end')
    if period_end:
        conditions.append('m.period_end <= %(period_end)s')
        params['period_end'] = period_end

    try:
        for key, col, op in [
            ('sl_min',       'm.sl_start', '>='),
            ('sl_max',       'm.sl_end',   '<='),
            ('lim_magn_min', 'm.lim_mag',  '>='),
            ('lim_magn_max', 'm.lim_mag',  '<='),
        ]:
            val = args.get(key)
            if val is not None:
                conditions.append(f'{col} {op} %({key})s')
                params[key] = float(val)

        session_ids = args.getlist('session_id')
        if session_ids:
            phs = ', '.join(f'%(sess_{i})s' for i in range(len(session_ids)))
            conditions.append(f'm.session_id IN ({phs})')
            for i, sid in enumerate(session_ids):
                params[f'sess_{i}'] = int(sid)

        magn_ids = args.getlist('magn_id')
        if magn_ids:
            phs = ', '.join(f'%(magn_{i})s' for i in range(len(magn_ids)))
            conditions.append(f'm.id IN ({phs})')
            for i, mid in enumerate(magn_ids):
                params[f'magn_{i}'] = int(mid)

    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid parameter value: {exc}')

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


@api_bp.route('/rates')
def get_rates():
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return jsonify({'error': 'No database configured.'}), 503

    try:
        conditions, params = _build_rate_conditions(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    stmt = db_conn = None
    select = """
        SELECT
            r.id,
            r.shower,
            r.period_start,
            r.period_end,
            r.sl_start,
            r.sl_end,
            r.session_id,
            r.freq,
            r.lim_mag,
            r.t_eff,
            r.f,
            r.sidereal_time,
            r.sun_alt,
            r.sun_az,
            r.moon_alt,
            r.moon_az,
            r.moon_illum,
            r.field_alt,
            r.field_az,
            r.rad_alt,
            r.rad_az,
            rm.magn_id
        FROM rate r
        LEFT JOIN rate_magnitude rm ON r.id = rm.rate_id
    """
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    stmt = f'{select} {where}'

    includes = {x.strip() for x in request.args.get('include', '').split(',') if x.strip()}

    db_conn = _get_db(config)
    try:
        cur = db_conn.cursor()
        cur.execute(db_conn.convert_stmt(stmt), params)
        observations = _rows_to_dicts(cur)

        result = {'observations': observations}

        if 'sessions' in includes:
            session_ids = list({r['session_id'] for r in observations if r['session_id'] is not None})
            result['sessions'] = _fetch_sessions(db_conn, session_ids) if session_ids else []

        if 'magnitudes' in includes:
            magn_ids = list({r['magn_id'] for r in observations if r['magn_id'] is not None})
            result['magnitudes'] = _fetch_magnitude_details(db_conn, magn_ids) if magn_ids else []

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(result)


@api_bp.route('/magnitudes')

def get_magnitudes():
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return jsonify({'error': 'No database configured.'}), 503

    try:
        conditions, params = _build_magnitude_conditions(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    select = """
        SELECT
            m.id,
            m.shower,
            m.period_start,
            m.period_end,
            m.sl_start,
            m.sl_end,
            m.session_id,
            m.freq,
            m.mean,
            m.lim_mag
        FROM magnitude m
    """
    where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
    stmt = f'{select} {where}'

    includes = {x.strip() for x in request.args.get('include', '').split(',') if x.strip()}

    db_conn = _get_db(config)
    try:
        cur = db_conn.cursor()
        cur.execute(db_conn.convert_stmt(stmt), params)
        observations = _rows_to_dicts(cur)

        result = {'observations': observations}

        if 'sessions' in includes:
            session_ids = list({r['session_id'] for r in observations if r['session_id'] is not None})
            result['sessions'] = _fetch_sessions(db_conn, session_ids) if session_ids else []

        if 'magnitudes' in includes:
            magn_ids = list({r['id'] for r in observations if r['id'] is not None})
            result['magnitudes'] = _fetch_magnitude_details(db_conn, magn_ids) if magn_ids else []

    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(result)


@api_bp.route('/showers')
def get_showers():
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return jsonify({'error': 'No database configured.'}), 503

    db_conn = _get_db(config)
    try:
        cur = db_conn.cursor()
        cur.execute("""
            SELECT
                iau_code,
                name,
                start_month,
                start_day,
                end_month,
                end_day,
                peak_month,
                peak_day,
                ra,
                "dec",
                v,
                r,
                zhr
            FROM shower
            ORDER BY iau_code
        """)
        showers = _rows_to_dicts(cur)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(showers)


@api_bp.route('/openapi.yaml')
def openapi_spec():
    if not os.path.isfile(_OPENAPI_FILE):
        return 'OpenAPI specification not found.', 404
    return send_from_directory(
        os.path.dirname(_OPENAPI_FILE),
        os.path.basename(_OPENAPI_FILE),
        mimetype='application/yaml',
    )
