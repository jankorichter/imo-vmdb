import argparse
import os
import tempfile
from configparser import RawConfigParser

from flask import Flask

from imo_vmdb.command import config_factory
from imo_vmdb.restapi import api_bp
from imo_vmdb.webui.jobs import JobManager


def create_app(config: RawConfigParser, upload_dir: str) -> Flask:
    """Create and configure the Flask application.

    Registers the main web UI blueprint and the REST API blueprint at
    ``/api/v1``, and stores the config, upload directory, and a fresh
    :class:`~imo_vmdb.webui.jobs.JobManager` on the app config.

    :param config: Parsed configuration (must have a ``[database]`` section).
    :param upload_dir: Directory for temporary CSV upload files.
    :return: Configured :class:`flask.Flask` application instance.
    """
    app = Flask(__name__, template_folder="webui/templates")
    app.config["IMO_CONFIG"] = config
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["JOB_MANAGER"] = JobManager()

    from imo_vmdb.webui.routes import bp

    app.register_blueprint(bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app


def main(args=None):
    """Parse CLI arguments and start the Flask development server.

    Reads configuration via :func:`~imo_vmdb.command.config_factory`, resolves
    the bind port (CLI flag > config file ``[webui] port`` > default 8000),
    and runs the app with threading enabled.

    :param args: Argument list; defaults to ``sys.argv[1:]`` when ``None``.
    """
    parser = argparse.ArgumentParser(
        description="imo-vmdb web_server (Web UI and REST API)"
    )
    parser.add_argument(
        "-c",
        "--config",
        dest="config_file",
        help="Path to the configuration file (or set IMO_VMDB_CONFIG env var)",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port (default: 8000, or IMO_VMDB_WEBUI_PORT env var)",
    )
    options = parser.parse_args(args)

    config = config_factory(options, parser)

    port = (
        options.port
        if options.port is not None
        else config.getint("webui", "port", fallback=8000)
    )
    upload_dir = config.get("webui", "upload_dir", fallback=tempfile.gettempdir())
    os.makedirs(upload_dir, exist_ok=True)

    print(f" * imo-vmdb web server running on http://{options.host}:{port}")

    app = create_app(config, upload_dir)
    app.run(host=options.host, port=port, threaded=True)


if __name__ == "__main__":
    main()
