import csv
import io
import os
import uuid

from flask import Blueprint, Response, current_app, jsonify, make_response, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from imo_vmdb import export_table
from imo_vmdb.db import DBAdapter

bp = Blueprint('main', __name__)

_DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'built_docs')


def _db_factory(config):
    db_section = dict(config['database']) if config.has_section('database') else {}
    return lambda: DBAdapter(db_section)


def _get_db():
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return None, 'No database configured'
    return DBAdapter(dict(config['database'])), None


def _csv_response(content, filename):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return resp


def _table_to_csv(cols, rows):
    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow(cols)
    writer.writerows(rows)
    return out.getvalue()


def _export_table_route(table, filename, reimport=False):
    db_conn, err = _get_db()
    if err:
        return jsonify({'error': err}), 503
    try:
        cols, rows = export_table(db_conn, table, reimport=reimport)
    except Exception as exc:
        return jsonify({'error': str(exc)}), 503
    finally:
        db_conn.close()
    return _csv_response(_table_to_csv(cols, rows), filename)


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/docs/')
@bp.route('/docs/<path:filename>')
def docs(filename='index.html'):
    docs_dir = os.path.abspath(_DOCS_DIR)
    if not os.path.isdir(docs_dir):
        return 'Documentation not built.', 404
    return send_from_directory(docs_dir, filename)


@bp.route('/run/initdb', methods=['POST'])
def run_initdb():
    config = current_app.config['IMO_CONFIG']
    job_manager = current_app.config['JOB_MANAGER']
    job_id = job_manager.start_initdb(_db_factory(config))
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/normalize', methods=['POST'])
def run_normalize():
    config = current_app.config['IMO_CONFIG']
    job_manager = current_app.config['JOB_MANAGER']
    job_id = job_manager.start_normalize(_db_factory(config))
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/cleanup', methods=['POST'])
def run_cleanup():
    config = current_app.config['IMO_CONFIG']
    job_manager = current_app.config['JOB_MANAGER']
    job_id = job_manager.start_cleanup(_db_factory(config))
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/import_csv', methods=['POST'])
def run_import_csv():
    config = current_app.config['IMO_CONFIG']
    job_manager = current_app.config['JOB_MANAGER']
    upload_dir = current_app.config['UPLOAD_DIR']
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files provided.'}), 400

    saved_paths = []
    for f in files:
        if f.filename:
            filename = secure_filename(f.filename)
            path = os.path.join(upload_dir, f'{uuid.uuid4().hex}_{filename}')
            f.save(path)
            saved_paths.append(path)

    if not saved_paths:
        return jsonify({'error': 'No valid files provided.'}), 400

    do_delete = request.form.get('do_delete') == '1'
    is_permissive = request.form.get('is_permissive') == '1'
    try_repair = request.form.get('try_repair') == '1'

    job_id = job_manager.start_import(
        _db_factory(config), saved_paths,
        do_delete=do_delete, is_permissive=is_permissive, try_repair=try_repair,
    )
    if job_id is None:
        for path in saved_paths:
            try:
                os.unlink(path)
            except OSError:
                pass
        return jsonify({'error': 'Another job is already running.'}), 409

    return jsonify({'job_id': job_id})


@bp.route('/stream/<job_id>')
def stream(job_id):
    job_manager = current_app.config['JOB_MANAGER']
    log_iter = job_manager.iter_logs(job_id)
    if log_iter is None:
        return jsonify({'error': 'Unknown job.'}), 404

    def generate():
        for line in log_iter:
            safe = line.replace('\n', ' ')
            yield f'data: {safe}\n\n'
        yield 'event: done\ndata: \n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/status/<job_id>')
def status(job_id):
    job_manager = current_app.config['JOB_MANAGER']
    job_status = job_manager.get_status(job_id)
    if job_status is None:
        return jsonify({'error': 'Unknown job.'}), 404
    return jsonify(job_status)


@bp.route('/export/shower')
def export_shower():
    reimport = request.args.get('reimport') == '1'
    return _export_table_route('shower', 'shower.csv', reimport=reimport)


@bp.route('/export/radiant')
def export_radiant():
    reimport = request.args.get('reimport') == '1'
    return _export_table_route('radiant', 'radiant.csv', reimport=reimport)


@bp.route('/export/session')
def export_session():
    return _export_table_route('obs_session', 'session.csv')


@bp.route('/export/rate')
def export_rate():
    return _export_table_route('rate', 'rate.csv')


@bp.route('/export/rate_magnitude')
def export_rate_magnitude():
    return _export_table_route('rate_magnitude', 'rate_magnitude.csv')


@bp.route('/export/magnitude')
def export_magnitude():
    return _export_table_route('magnitude', 'magnitude.csv')


@bp.route('/export/magnitude_detail')
def export_magnitude_detail():
    return _export_table_route('magnitude_detail', 'magnitude_detail.csv')
