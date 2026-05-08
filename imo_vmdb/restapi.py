import dataclasses
import os

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from imo_vmdb import (
    DBAdapter,
    MagnitudeFilter,
    RateFilter,
    query_magnitudes,
    query_rates,
    query_showers,
)

api_bp = Blueprint("api", __name__)


def _serialize(obj):
    """Convert a dataclass to a JSON-serialisable dict, omitting ``None``-valued keys."""
    return {k: v for k, v in dataclasses.asdict(obj).items() if v is not None}


_OPENAPI_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "docs", "openapi.yaml")
)


def _get_db(config) -> DBAdapter:
    """Create a :class:`~imo_vmdb.db.DBAdapter` from the ``[database]`` config section.

    :param config: Parsed application configuration (``configparser.ConfigParser``).
    :return: Open database connection.
    """
    return DBAdapter(dict(config["database"]))


def _opt_float(val: str | None) -> float | None:
    """Convert a string to ``float``, or return ``None`` if *val* is ``None``.

    :param val: String value from a query parameter, or ``None``.
    :return: Parsed float, or ``None``.
    """
    return float(val) if val is not None else None


def _parse_includes(args) -> set[str]:
    """Parse the comma-separated ``include`` query parameter.

    :param args: Flask ``request.args`` mapping.
    :return: Set of lowercase, stripped include tokens (e.g. ``{'sessions', 'magnitudes'}``).
    """
    return {x.strip() for x in args.get("include", "").split(",") if x.strip()}


def _parse_rate_filter(args) -> RateFilter:
    """Build a :class:`~imo_vmdb.RateFilter` from Flask query parameters.

    Accepted parameters mirror the ``/api/v1/rates`` endpoint:
    ``shower`` (repeatable), ``period_start``, ``period_end``, ``sl_min``,
    ``sl_max``, ``lim_magn_min``, ``lim_magn_max``, ``sun_alt_max``,
    ``moon_alt_max``, ``session_id`` (repeatable), ``rate_id`` (repeatable),
    ``include`` (comma-separated: ``sessions``, ``magnitudes``).

    :param args: Flask ``request.args`` mapping.
    :return: Populated :class:`~imo_vmdb.RateFilter`.
    :raises ValueError: If any numeric parameter cannot be parsed.
    """
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
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid parameter value: {exc}")


def _parse_magnitude_filter(args) -> MagnitudeFilter:
    """Build a :class:`~imo_vmdb.MagnitudeFilter` from Flask query parameters.

    Accepted parameters mirror the ``/api/v1/magnitudes`` endpoint:
    ``shower`` (repeatable), ``period_start``, ``period_end``, ``sl_min``,
    ``sl_max``, ``lim_magn_min``, ``lim_magn_max``, ``session_id``
    (repeatable), ``magn_id`` (repeatable), ``include`` (comma-separated:
    ``sessions``, ``magnitudes``).

    :param args: Flask ``request.args`` mapping.
    :return: Populated :class:`~imo_vmdb.MagnitudeFilter`.
    :raises ValueError: If any numeric parameter cannot be parsed.
    """
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
        )
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid parameter value: {exc}")


@api_bp.route("/rates")
def get_rates():
    """Return rate observations filtered by optional query parameters.

    Query parameters: ``shower`` (repeatable), ``period_start``, ``period_end``,
    ``sl_min``, ``sl_max``, ``lim_magn_min``, ``lim_magn_max``, ``sun_alt_max``,
    ``moon_alt_max``, ``session_id`` (repeatable), ``rate_id`` (repeatable),
    ``include`` (comma-separated: ``sessions``, ``magnitudes``).

    :return: JSON object with an ``observations`` key (list of rate dicts).
        When ``include=sessions`` is requested, a ``sessions`` key is added.
        When ``include=magnitudes`` is requested, a ``magnitudes`` key is added.
    :statuscode 200: Query succeeded.
    :statuscode 400: A query parameter value could not be parsed.
    :statuscode 500: An unexpected server error occurred.
    :statuscode 503: No database is configured.
    """
    config = current_app.config["IMO_CONFIG"]
    if not config.has_section("database"):
        return jsonify({"error": "No database configured."}), 503

    try:
        f = _parse_rate_filter(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = query_rates(db_conn, f)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(_serialize(result))


@api_bp.route("/magnitudes")
def get_magnitudes():
    """Return magnitude observations filtered by optional query parameters.

    Query parameters: ``shower`` (repeatable), ``period_start``, ``period_end``,
    ``sl_min``, ``sl_max``, ``lim_magn_min``, ``lim_magn_max``,
    ``session_id`` (repeatable), ``magn_id`` (repeatable),
    ``include`` (comma-separated: ``sessions``, ``magnitudes``).

    :return: JSON object with an ``observations`` key (list of magnitude dicts).
        When ``include=sessions`` is requested, a ``sessions`` key is added.
        When ``include=magnitudes`` is requested, a ``magnitudes`` key is added.
    :statuscode 200: Query succeeded.
    :statuscode 400: A query parameter value could not be parsed.
    :statuscode 500: An unexpected server error occurred.
    :statuscode 503: No database is configured.
    """
    config = current_app.config["IMO_CONFIG"]
    if not config.has_section("database"):
        return jsonify({"error": "No database configured."}), 503

    try:
        f = _parse_magnitude_filter(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    db_conn = _get_db(config)
    try:
        result = query_magnitudes(db_conn, f)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify(_serialize(result))


@api_bp.route("/showers")
def get_showers():
    """Return all meteor showers from the reference catalogue.

    :return: JSON array of shower objects.  Each object contains the keys
        ``iau_code``, ``name``, ``start_month``, ``start_day``, ``end_month``,
        ``end_day``, ``peak_month``, ``peak_day``, ``ra``, ``dec``, ``v``,
        ``r``, ``zhr``.
    :statuscode 200: Query succeeded.
    :statuscode 500: An unexpected server error occurred.
    :statuscode 503: No database is configured.
    """
    config = current_app.config["IMO_CONFIG"]
    if not config.has_section("database"):
        return jsonify({"error": "No database configured."}), 503

    db_conn = _get_db(config)
    try:
        showers = query_showers(db_conn)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        db_conn.close()

    return jsonify([dataclasses.asdict(s) for s in showers])


@api_bp.route("/openapi.yaml")
def openapi_spec():
    """Serve the OpenAPI 3.1 specification as ``application/yaml``.

    :return: YAML file content with MIME type ``application/yaml``.
    :statuscode 200: File found and returned.
    :statuscode 404: The OpenAPI specification file does not exist.
    """
    if not os.path.isfile(_OPENAPI_FILE):
        return "OpenAPI specification not found.", 404
    return send_from_directory(
        os.path.dirname(_OPENAPI_FILE),
        os.path.basename(_OPENAPI_FILE),
        mimetype="application/yaml",
    )
