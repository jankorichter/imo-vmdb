import dataclasses
import datetime
import json
import os

import yaml
from flask import Blueprint, current_app, jsonify, request, send_from_directory

from imo_vmdb import (
    DBAdapter,
    DBException,
    Magnitude,
    MagnitudeFilter,
    MagnitudeService,
    Rate,
    RateFilter,
    RateService,
    SessionFilter,
    SessionService,
    ShowerService,
    StatsService,
)

api_bp = Blueprint("api", __name__)


def _serialize(obj):
    """Convert a dataclass to a JSON-serialisable dict, omitting ``None``-valued keys."""
    return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}


def _serialize_filtered(obj, fields: set[str] | None):
    """Serialize a dataclass and optionally restrict to *fields*.

    Unlike :func:`_serialize`, this keeps explicit ``None`` values when the
    caller has selected the field — they are part of the requested response shape.
    """
    raw = dataclasses.asdict(obj)
    if fields is None:
        return {k: v for k, v in raw.items() if v is not None}
    return {k: raw[k] for k in fields if k in raw}


_OPENAPI_FILE = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "data", "openapi.yaml"
)


def _get_db(config) -> DBAdapter:
    """Create a :class:`~imo_vmdb.db.DBAdapter` from the ``[database]`` config section."""
    return DBAdapter(dict(config["database"]))


def _require_db():
    """Return a config object if ``[database]`` is present, else a 503 response."""
    config = current_app.config["IMO_CONFIG"]
    if not config.has_section("database"):
        return None, (jsonify({"error": "No database configured."}), 503)
    return config, None


def _opt_float(val: str | None) -> float | None:
    return float(val) if val is not None else None


def _opt_int(val: str | None) -> int | None:
    return int(val) if val is not None else None


def _parse_includes(args) -> set[str]:
    return {x.strip() for x in args.get("include", "").split(",") if x.strip()}


def _parse_fields(args, allowed: set[str]) -> set[str] | None:
    raw = args.get("fields")
    if raw is None:
        return None
    parsed = {x.strip() for x in raw.split(",") if x.strip()}
    unknown = parsed - allowed
    if unknown:
        raise ValueError(
            f"Unknown field(s): {sorted(unknown)} (allowed: {sorted(allowed)})"
        )
    return parsed


def _dataclass_field_names(cls) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def _parse_rate_filter(args) -> RateFilter:
    """Build a :class:`~imo_vmdb.RateFilter` from Flask query parameters."""
    try:
        includes = _parse_includes(args)
        return RateFilter(
            showers=args.getlist("shower"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
            sl_min=_opt_float(args.get("sl_min")),
            sl_max=_opt_float(args.get("sl_max")),
            lim_magn_min=_opt_float(args.get("lim_magn_min")),
            lim_magn_max=_opt_float(args.get("lim_magn_max")),
            sun_alt_max=_opt_float(args.get("sun_alt_max")),
            moon_alt_max=_opt_float(args.get("moon_alt_max")),
            session_ids=[int(x) for x in args.getlist("session_id")],
            rate_ids=[int(x) for x in args.getlist("rate_id")],
            include_sessions="sessions" in includes,
            include_magnitudes="magnitudes" in includes,
            limit=_opt_int(args.get("limit")),
            offset=_opt_int(args.get("offset")),
            order_by=args.get("order_by"),
            order=args.get("order"),
            with_total=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid parameter value: {exc}")


def _parse_magnitude_filter(args) -> MagnitudeFilter:
    """Build a :class:`~imo_vmdb.MagnitudeFilter` from Flask query parameters."""
    try:
        includes = _parse_includes(args)
        return MagnitudeFilter(
            showers=args.getlist("shower"),
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
            sl_min=_opt_float(args.get("sl_min")),
            sl_max=_opt_float(args.get("sl_max")),
            lim_magn_min=_opt_float(args.get("lim_magn_min")),
            lim_magn_max=_opt_float(args.get("lim_magn_max")),
            session_ids=[int(x) for x in args.getlist("session_id")],
            magn_ids=[int(x) for x in args.getlist("magn_id")],
            include_sessions="sessions" in includes,
            include_magnitudes="magnitudes" in includes,
            limit=_opt_int(args.get("limit")),
            offset=_opt_int(args.get("offset")),
            order_by=args.get("order_by"),
            order=args.get("order"),
            with_total=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid parameter value: {exc}")


def _parse_session_filter(args) -> SessionFilter:
    try:
        return SessionFilter(
            observer_ids=[int(x) for x in args.getlist("observer_id")],
            period_start=args.get("period_start"),
            period_end=args.get("period_end"),
            limit=_opt_int(args.get("limit")),
            offset=_opt_int(args.get("offset")),
            order_by=args.get("order_by"),
            order=args.get("order"),
            with_total=True,
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid parameter value: {exc}")


def _with_total_header(payload, total: int | None):
    """Wrap a JSON payload with an ``X-Total-Count`` header."""
    response = jsonify(payload)
    if total is not None:
        response.headers["X-Total-Count"] = str(total)
    return response


@api_bp.route("/rates")
def get_rates():
    """Return rate observations filtered by optional query parameters."""
    config, err = _require_db()
    if err:
        return err

    try:
        f = _parse_rate_filter(request.args)
        fields = _parse_fields(request.args, _dataclass_field_names(Rate))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = RateService(db_conn).query(f)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    body = {
        "observations": [_serialize_filtered(o, fields) for o in result.observations]
    }
    if result.sessions is not None:
        body["sessions"] = [_serialize(s) for s in result.sessions]
    if result.magnitudes is not None:
        body["magnitudes"] = [_serialize(m) for m in result.magnitudes]

    return _with_total_header(body, result.total)


@api_bp.route("/rates/<int:rate_id>")
def get_rate(rate_id: int):
    """Return a single rate observation."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        rate = RateService(db_conn).by_id(rate_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    if rate is None:
        return jsonify({"error": "Rate not found."}), 404
    return jsonify(_serialize(rate))


@api_bp.route("/magnitudes")
def get_magnitudes():
    """Return magnitude observations filtered by optional query parameters."""
    config, err = _require_db()
    if err:
        return err

    try:
        f = _parse_magnitude_filter(request.args)
        fields = _parse_fields(request.args, _dataclass_field_names(Magnitude))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = MagnitudeService(db_conn).query(f)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    body = {
        "observations": [_serialize_filtered(o, fields) for o in result.observations]
    }
    if result.sessions is not None:
        body["sessions"] = [_serialize(s) for s in result.sessions]
    if result.magnitudes is not None:
        body["magnitudes"] = [_serialize(m) for m in result.magnitudes]

    return _with_total_header(body, result.total)


@api_bp.route("/magnitudes/<int:magn_id>")
def get_magnitude(magn_id: int):
    """Return a single magnitude observation."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        magn = MagnitudeService(db_conn).by_id(magn_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    if magn is None:
        return jsonify({"error": "Magnitude not found."}), 404
    return jsonify(_serialize(magn))


@api_bp.route("/sessions")
def get_sessions():
    """Return observation sessions matching optional filters."""
    config, err = _require_db()
    if err:
        return err

    try:
        f = _parse_session_filter(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = SessionService(db_conn).query(f)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    body = {"sessions": [_serialize(s) for s in result.observations]}
    return _with_total_header(body, result.total)


@api_bp.route("/sessions/<int:session_id>")
def get_session(session_id: int):
    """Return a single observation session."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        session = SessionService(db_conn).by_id(session_id)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    if session is None:
        return jsonify({"error": "Session not found."}), 404
    return jsonify(_serialize(session))


@api_bp.route("/showers")
def get_showers():
    """Return all meteor showers from the reference catalogue."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        showers = ShowerService(db_conn).query()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(s) for s in showers])


@api_bp.route("/showers/active")
def get_active_showers():
    """Return showers whose activity period covers the given date (default: today UTC)."""
    config, err = _require_db()
    if err:
        return err

    raw = request.args.get("date")
    try:
        on_date = (
            datetime.date.fromisoformat(raw)
            if raw
            else datetime.datetime.now(datetime.timezone.utc).date()
        )
    except ValueError as exc:
        return jsonify({"error": f"Invalid date: {exc}"}), 400

    db_conn = _get_db(config)
    try:
        showers = ShowerService(db_conn).active(on_date)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(s) for s in showers])


@api_bp.route("/showers/<iau_code>")
def get_shower(iau_code: str):
    """Return a single shower by IAU code."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        shower = ShowerService(db_conn).by_code(iau_code)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    if shower is None:
        return jsonify({"error": "Shower not found."}), 404
    return jsonify(dataclasses.asdict(shower))


@api_bp.route("/showers/<iau_code>/radiants")
def get_shower_radiants(iau_code: str):
    """Return all radiant entries for the given shower, ordered by (month, day)."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        radiants = ShowerService(db_conn).radiants(iau_code)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(r) for r in radiants])


@api_bp.route("/stats/meta")
def get_stats_meta():
    """Return database scope summary (counts and covered date range)."""
    config, err = _require_db()
    if err:
        return err

    db_conn = _get_db(config)
    try:
        meta = StatsService(db_conn).meta()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(dataclasses.asdict(meta))


def _stats_period_args():
    return request.args.get("period_start"), request.args.get("period_end")


@api_bp.route("/stats/by-shower")
def get_stats_by_shower():
    config, err = _require_db()
    if err:
        return err

    period_start, period_end = _stats_period_args()
    db_conn = _get_db(config)
    try:
        rows = StatsService(db_conn).by_shower(period_start, period_end)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(r) for r in rows])


@api_bp.route("/stats/by-country")
def get_stats_by_country():
    config, err = _require_db()
    if err:
        return err

    period_start, period_end = _stats_period_args()
    db_conn = _get_db(config)
    try:
        rows = StatsService(db_conn).by_country(period_start, period_end)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(r) for r in rows])


@api_bp.route("/stats/by-year")
def get_stats_by_year():
    config, err = _require_db()
    if err:
        return err

    period_start, period_end = _stats_period_args()
    db_conn = _get_db(config)
    try:
        rows = StatsService(db_conn).by_year(period_start, period_end)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(r) for r in rows])


@api_bp.route("/health")
def health():
    """Liveness/readiness probe.

    Returns 200 with ``{"status": "ok", "database": "ok"}`` when the
    database is reachable, 503 with ``{"status": "degraded", "database": <reason>}``
    otherwise.  Suitable for load balancers and Kubernetes probes.
    """
    config = current_app.config["IMO_CONFIG"]
    if not config.has_section("database"):
        return (
            jsonify({"status": "degraded", "database": "no database configured"}),
            503,
        )
    try:
        db_conn = DBAdapter(dict(config["database"]))
    except Exception as exc:
        return jsonify({"status": "degraded", "database": str(exc)}), 503
    try:
        db_conn.ping()
        return jsonify({"status": "ok", "database": "ok"})
    except DBException as exc:
        return jsonify({"status": "degraded", "database": str(exc)}), 503
    finally:
        db_conn.close()


@api_bp.route("/openapi.yaml")
def openapi_spec():
    """Serve the OpenAPI 3.1 specification as ``application/yaml``."""
    if not os.path.isfile(_OPENAPI_FILE):
        return "OpenAPI specification not found.", 404
    return send_from_directory(
        os.path.dirname(_OPENAPI_FILE),
        os.path.basename(_OPENAPI_FILE),
        mimetype="application/yaml",
    )


@api_bp.route("/openapi.json")
def openapi_spec_json():
    """Serve the OpenAPI 3.1 specification as ``application/json``."""
    if not os.path.isfile(_OPENAPI_FILE):
        return "OpenAPI specification not found.", 404
    with open(_OPENAPI_FILE, encoding="utf-8") as fh:
        spec = yaml.safe_load(fh)
    return current_app.response_class(
        json.dumps(spec, indent=2),
        mimetype="application/json",
    )
