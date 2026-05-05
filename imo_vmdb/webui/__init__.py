from configparser import RawConfigParser

from flask import Flask

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
    app = Flask(__name__, template_folder="templates")
    app.config["IMO_CONFIG"] = config
    app.config["UPLOAD_DIR"] = upload_dir
    app.config["JOB_MANAGER"] = JobManager()
    from .routes import bp

    app.register_blueprint(bp)
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    return app
