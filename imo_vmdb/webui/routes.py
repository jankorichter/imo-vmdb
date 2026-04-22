import csv
import io
import logging
import os
import queue
import threading
import uuid
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, make_response, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

import imo_vmdb
from imo_vmdb.db import DBAdapter

_DATA_DIR = Path(os.path.dirname(os.path.realpath(__file__))).parent / 'data'

bp = Blueprint('main', __name__)

_jobs = {}
_jobs_lock = threading.Lock()


class _QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.queue = q

    def emit(self, record):
        self.queue.put(self.format(record))


def _make_logger(job_id):
    q = _jobs[job_id]['queue']
    handler = _QueueHandler(q)
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s', None, '%'))
    logger = logging.getLogger(f'imo_vmdb.job.{job_id}')
    logger.handlers = []
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def _finish_job(job_id, exit_code):
    with _jobs_lock:
        _jobs[job_id]['running'] = False
        _jobs[job_id]['exit_code'] = exit_code
    _jobs[job_id]['queue'].put(None)


def _run_job(job_id, fn, config, extra_args):
    logger = _make_logger(job_id)
    try:
        db_section = dict(config['database']) if config.has_section('database') else {}
        db_conn = DBAdapter(db_section)
        try:
            exit_code = fn(db_conn, logger, *extra_args)
            db_conn.commit()
        finally:
            db_conn.close()
    except Exception as exc:
        logger.critical('Unexpected error: %s', exc)
        exit_code = 100
    _finish_job(job_id, exit_code if exit_code is not None else 0)


def _run_import_job(job_id, config, file_paths, do_delete, is_permissive, try_repair):
    logger = _make_logger(job_id)
    try:
        db_section = dict(config['database']) if config.has_section('database') else {}
        db_conn = DBAdapter(db_section)
        try:
            importer = imo_vmdb.CSVImporter(
                db_conn, logger,
                do_delete=do_delete,
                try_repair=try_repair,
                is_permissive=is_permissive,
            )
            importer.run(file_paths)
            db_conn.commit()
            exit_code = int(importer.has_errors)
        finally:
            db_conn.close()
    except Exception as exc:
        logger.critical('Unexpected error: %s', exc)
        exit_code = 100
    finally:
        for path in file_paths:
            try:
                os.unlink(path)
            except OSError:
                pass
    _finish_job(job_id, exit_code)


def _start_job(target, *args):
    with _jobs_lock:
        if any(j['running'] for j in _jobs.values()):
            return None
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {'queue': queue.Queue(), 'running': True, 'exit_code': None}

    t = threading.Thread(target=target, args=(job_id,) + args, daemon=True)
    t.start()
    return job_id


_DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'docs', '_build', 'html')


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
    job_id = _start_job(_run_job, imo_vmdb.initdb, config, ())
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/normalize', methods=['POST'])
def run_normalize():
    config = current_app.config['IMO_CONFIG']
    job_id = _start_job(_run_job, imo_vmdb.normalize, config, ())
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/cleanup', methods=['POST'])
def run_cleanup():
    config = current_app.config['IMO_CONFIG']
    job_id = _start_job(_run_job, imo_vmdb.cleanup, config, ())
    if job_id is None:
        return jsonify({'error': 'Another job is already running.'}), 409
    return jsonify({'job_id': job_id})


@bp.route('/run/import_csv', methods=['POST'])
def run_import_csv():
    config = current_app.config['IMO_CONFIG']
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

    job_id = _start_job(_run_import_job, config, saved_paths, do_delete, is_permissive, try_repair)
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
    if job_id not in _jobs:
        return jsonify({'error': 'Unknown job.'}), 404

    def generate():
        q = _jobs[job_id]['queue']
        while True:
            line = q.get()
            if line is None:
                yield 'event: done\ndata: \n\n'
                break
            safe = line.replace('\n', ' ')
            yield f'data: {safe}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@bp.route('/status/<job_id>')
def status(job_id):
    if job_id not in _jobs:
        return jsonify({'error': 'Unknown job.'}), 404
    job = _jobs[job_id]
    return jsonify({'running': job['running'], 'exit_code': job['exit_code']})


def _csv_response(content, filename):
    resp = make_response(content)
    resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
    resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return resp


def _export_static(filename):
    with open(_DATA_DIR / filename, 'r', encoding='utf-8-sig') as f:
        return f.read()


def _export_db_table(table):
    config = current_app.config['IMO_CONFIG']
    if not config.has_section('database'):
        return None, 'No database configured'
    db_conn = DBAdapter(dict(config['database']))
    try:
        cur = db_conn.cursor()
        cur.execute(f'SELECT * FROM {table}')
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
    except Exception as exc:
        return None, str(exc)
    finally:
        db_conn.close()
    out = io.StringIO()
    csv.writer(out, delimiter=';').writerow(cols)
    csv.writer(out, delimiter=';').writerows(rows)
    return out.getvalue(), None



@bp.route('/export/shower')
def export_shower():
    if request.args.get('reimport') == '1':
        return _csv_response(_export_static('showers.csv'), 'showers.csv')
    content, err = _export_db_table('shower')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'shower.csv')


@bp.route('/export/radiant')
def export_radiant():
    if request.args.get('reimport') == '1':
        return _csv_response(_export_static('radiants.csv'), 'radiants.csv')
    content, err = _export_db_table('radiant')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'radiant.csv')


@bp.route('/export/session')
def export_session():
    content, err = _export_db_table('obs_session')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'session.csv')


@bp.route('/export/rate')
def export_rate():
    content, err = _export_db_table('rate')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'rate.csv')


@bp.route('/export/rate_magnitude')
def export_rate_magnitude():
    content, err = _export_db_table('rate_magnitude')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'rate_magnitude.csv')


@bp.route('/export/magnitude')
def export_magnitude():
    content, err = _export_db_table('magnitude')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'magnitude.csv')


@bp.route('/export/magnitude_detail')
def export_magnitude_detail():
    content, err = _export_db_table('magnitude_detail')
    if err:
        return jsonify({'error': err}), 503
    return _csv_response(content, 'magnitude_detail.csv')
