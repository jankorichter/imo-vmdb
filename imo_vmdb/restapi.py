import os

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from imo_vmdb.db import DBAdapter
from imo_vmdb.server import MagnitudeFilter, RateFilter, query_magnitudes, query_rates, query_showers

api_bp = Blueprint('api', __name__)

_OPENAPI_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'docs', 'openapi.yaml')
)


def _get_db(config):
    return DBAdapter(dict(config['database']))


def _opt_float(val):
    return float(val) if val is not None else None


def _parse_includes(args):
    return {x.strip() for x in args.get('include', '').split(',') if x.strip()}


def _parse_rate_filter(args) -> RateFilter:
    try:
        includes = _parse_includes(args)
        return RateFilter(
            showers=args.getlist('shower'),
            period_start=args.get('period_start'),
            period_end=args.get('period_end'),
            sl_min=_opt_float(args.get('sl_min')),
            sl_max=_opt_float(args.get('sl_max')),
            lim_magn_min=_opt_float(args.get('lim_magn_min')),
            lim_magn_max=_opt_float(args.get('lim_magn_max')),
            sun_alt_max=_opt_float(args.get('sun_alt_max')),
            moon_alt_max=_opt_float(args.get('moon_alt_max')),
            session_ids=[int(x) for x in args.getlist('session_id')],
            rate_ids=[int(x) for x in args.getlist('rate_id')],
            include_sessions='sessions' in includes,
            include_magnitudes='magnitudes' in includes,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid parameter value: {exc}')


def _parse_magnitude_filter(args) -> MagnitudeFilter:
    try:
        includes = _parse_includes(args)
        return MagnitudeFilter(
            showers=args.getlist('shower'),
            period_start=args.get('period_start'),
            period_end=args.get('period_end'),
            sl_min=_opt_float(args.get('sl_min')),
            sl_max=_opt_float(args.get('sl_max')),
            lim_magn_min=_opt_float(args.get('lim_magn_min')),
            lim_magn_max=_opt_float(args.get('lim_magn_max')),
            session_ids=[int(x) for x in args.getlist('session_id')],
            magn_ids=[int(x) for x in args.getlist('magn_id')],
            include_sessions='sessions' in includes,
            include_magnitudes='magnitudes' in includes,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f'Invalid parameter value: {exc}')


@api_bp.route('/rates')
def get_rates():
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return jsonify({'error': 'No database configured.'}), 503

    try:
        f = _parse_rate_filter(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = query_rates(db_conn, f)
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
        f = _parse_magnitude_filter(request.args)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = query_magnitudes(db_conn, f)
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
        showers = query_showers(db_conn)
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
