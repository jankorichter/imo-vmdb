from flask import Flask


def create_app(config, upload_dir):
    app = Flask(__name__, template_folder='templates')
    app.config['IMO_CONFIG'] = config
    app.config['UPLOAD_DIR'] = upload_dir
    from .routes import bp
    from .api import api_bp
    app.register_blueprint(bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    return app
