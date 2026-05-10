import argparse
import os
import sqlite3
import tempfile
from configparser import RawConfigParser

from flask import Flask, jsonify, send_file

from imo_vmdb import DBAdapter, DBException, export_db
from imo_vmdb.command import config_factory
from imo_vmdb.restapi import api_bp


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def create_app(
    config: RawConfigParser, upload_dir: str, enable_webui: bool = False
) -> Flask:
    """Create and configure the Flask application.

    Always registers the REST API blueprint at ``/api/v1``.  When
    ``enable_webui`` is ``True``, additionally registers the Web UI
    blueprint and stores a fresh :class:`~imo_vmdb.webui.jobs.JobManager`
    plus the upload directory on the app config.

    :param config: Parsed configuration (must have a ``[database]`` section).
    :param upload_dir: Directory for temporary CSV upload files (only used
        when ``enable_webui`` is ``True``).
    :param enable_webui: Register the Web UI blueprint and JobManager.
    :return: Configured :class:`flask.Flask` application instance.
    """
    app = Flask(__name__, template_folder="webui/templates")
    app.config["IMO_CONFIG"] = config

    if enable_webui:
        from imo_vmdb.webui.jobs import JobManager
        from imo_vmdb.webui.routes import bp

        app.config["UPLOAD_DIR"] = upload_dir
        app.config["JOB_MANAGER"] = JobManager()
        app.register_blueprint(bp)

    app.register_blueprint(api_bp, url_prefix="/api/v1")
    _register_download_routes(app)
    return app


def _register_download_routes(app: Flask) -> None:
    """Register binary download routes that live outside ``/api/v1``.

    These routes are always available when a database is configured —
    independent of whether the Web UI is enabled — so that programmers
    can fetch downloads directly via HTTP.
    """

    @app.route("/download/db")
    def download_db():
        config = app.config["IMO_CONFIG"]
        if not config.has_section("database"):
            return jsonify({"error": "No database configured"}), 503

        try:
            src = DBAdapter(dict(config["database"]))
        except DBException as exc:
            return jsonify({"error": f"Database error: {exc}"}), 503

        fd, tmp_path = tempfile.mkstemp(suffix=".sqlite", prefix="imo_vmdb_export_")
        os.close(fd)
        try:
            dst_conn = sqlite3.connect(tmp_path)
            try:
                export_db(src, dst_conn)
            finally:
                dst_conn.close()
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        finally:
            src.close()

        response = send_file(
            tmp_path,
            mimetype="application/vnd.sqlite3",
            as_attachment=True,
            download_name="imo_vmdb.sqlite",
        )
        response.call_on_close(lambda: os.path.exists(tmp_path) and os.unlink(tmp_path))
        return response


def wsgi_app():
    """WSGI app factory for Gunicorn ``--factory`` mode.

    Configuration is read from the ``IMO_VMDB_CONFIG`` environment variable
    (path to an INI file) or from ``IMO_VMDB_DATABASE_*`` etc. directly.
    Host and port are controlled by Gunicorn's ``--bind`` flag.

    The Web UI is opt-in: set ``IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true`` to
    enable it.  By default only the REST API is served.

    Example::

        gunicorn --workers 1 --threads 4 "imo_vmdb.httpd:wsgi_app()"

    .. warning::

        Always use ``--workers 1``.  The :class:`~imo_vmdb.webui.jobs.JobManager`
        stores job state in-process; multiple workers would make jobs invisible
        across processes, breaking status polling and log streaming.
    """
    upload_dir = os.environ.get("IMO_VMDB_WEBSERVER_UPLOAD_DIR", tempfile.gettempdir())
    enable_webui = _env_truthy("IMO_VMDB_WEBSERVER_ENABLE_WEBUI")
    config = config_factory(
        argparse.Namespace(config_file=None), argparse.ArgumentParser()
    )
    if enable_webui:
        os.makedirs(upload_dir, exist_ok=True)
    return create_app(config, upload_dir, enable_webui=enable_webui)


def main(args=None):
    """Parse CLI arguments and start the Flask development server.

    Reads configuration via :func:`~imo_vmdb.command.config_factory`,
    resolves the bind host (CLI flag > ``IMO_VMDB_WEBSERVER_HOST`` env >
    ``[webserver] host`` > ``127.0.0.1``) and bind port (CLI flag >
    ``IMO_VMDB_WEBSERVER_PORT`` env > ``[webserver] port`` > ``8000``),
    and runs the app with threading enabled.

    The Web UI is opt-in: pass ``--enable-webui`` (or set
    ``IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true`` /
    ``[webserver] enable_webui = true``) to enable it.  By default only
    the REST API is served.

    :param args: Argument list; defaults to ``sys.argv[1:]`` when ``None``.
    """
    parser = argparse.ArgumentParser(
        description="imo-vmdb web_server (REST API; Web UI optional via --enable-webui)"
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        help="Path to the configuration file (or set IMO_VMDB_CONFIG env var)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Bind host (default: 127.0.0.1, or IMO_VMDB_WEBSERVER_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: 8000, or IMO_VMDB_WEBSERVER_PORT env var)",
    )
    parser.add_argument(
        "--enable-webui",
        dest="enable_webui",
        action="store_true",
        default=False,
        help="Enable the Web UI in addition to the REST API",
    )
    options = parser.parse_args(args)

    config = config_factory(options, parser)

    host = (
        options.host
        if options.host is not None
        else config.get("webserver", "host", fallback="127.0.0.1")
    )
    port = (
        options.port
        if options.port is not None
        else config.getint("webserver", "port", fallback=8000)
    )
    upload_dir = config.get("webserver", "upload_dir", fallback=tempfile.gettempdir())
    enable_webui = options.enable_webui or config.getboolean(
        "webserver", "enable_webui", fallback=False
    )
    if enable_webui:
        os.makedirs(upload_dir, exist_ok=True)

    suffix = " with Web UI" if enable_webui else " (REST API only)"
    print(f" * imo-vmdb web server running on http://{host}:{port}{suffix}")

    app = create_app(config, upload_dir, enable_webui=enable_webui)
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
