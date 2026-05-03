from flask import Flask

from imo_vmdb.restapi import api_bp
from imo_vmdb.server import JobManager


def create_app(config, upload_dir):
    app = Flask(__name__, template_folder='templates')
    app.config['IMO_CONFIG'] = config
    app.config['UPLOAD_DIR'] = upload_dir
    app.config['JOB_MANAGER'] = JobManager()
    from .routes import bp
    app.register_blueprint(bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    return app
