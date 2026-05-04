import csv
import io
import logging
import os
import queue
import threading
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import imo_vmdb
from imo_vmdb.db import DBAdapter


class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue[str]) -> None:
        super().__init__()
        self.queue = q

    def emit(self, record: logging.LogRecord) -> None:
        self.queue.put(self.format(record))


class JobManager:
    """Manages long-running background jobs (initdb, normalize, cleanup, import, export).

    At most one job runs at a time. Start methods return ``None`` if another
    job is already running. Use :meth:`get_status` and :meth:`iter_logs` to
    monitor progress.

    .. note::
        Completed job records remain in memory for the lifetime of the
        ``JobManager`` instance. In long-running servers, consider creating
        a new instance periodically or limiting the number of jobs started.
    """

    def __init__(self):
        self._jobs = {}
        self._lock = threading.Lock()

    def _make_logger(self, job_id: str) -> logging.Logger:
        q = self._jobs[job_id]["queue"]
        handler = _QueueHandler(q)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(name)s] %(message)s", None, "%"
            )
        )
        logger = logging.getLogger(f"imo_vmdb.job.{job_id}")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        return logger

    def _finish_job(self, job_id: str, exit_code: int) -> None:
        with self._lock:
            self._jobs[job_id]["running"] = False
            self._jobs[job_id]["exit_code"] = exit_code
        self._jobs[job_id]["queue"].put(None)

    def _allocate_job(self) -> str | None:
        with self._lock:
            if any(j["running"] for j in self._jobs.values()):
                return None
            job_id = str(uuid.uuid4())
            self._jobs[job_id] = {
                "queue": queue.Queue(),
                "running": True,
                "exit_code": None,
            }
        return job_id

    def _run_simple(
        self,
        job_id: str,
        fn: Callable[[DBAdapter, logging.Logger], int | None],
        db_conn_factory: Callable[[], DBAdapter],
    ) -> None:
        logger = self._make_logger(job_id)
        try:
            db_conn = db_conn_factory()
            try:
                exit_code = fn(db_conn, logger)
                db_conn.commit()
            finally:
                db_conn.close()
        except Exception as exc:
            logger.critical("Unexpected error: %s", exc)
            exit_code = 100
        self._finish_job(job_id, exit_code if exit_code is not None else 0)

    def _run_import(
        self,
        job_id: str,
        db_conn_factory: Callable[[], DBAdapter],
        file_paths: list[str],
        do_delete: bool,
        is_permissive: bool,
        try_repair: bool,
    ) -> None:
        logger = self._make_logger(job_id)
        try:
            db_conn = db_conn_factory()
            try:
                importer = imo_vmdb.CSVImporter(
                    db_conn,
                    logger,
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
            logger.critical("Unexpected error: %s", exc)
            exit_code = 100
        finally:
            for path in file_paths:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        self._finish_job(job_id, exit_code)

    def _run_export(
        self,
        job_id: str,
        db_conn_factory: Callable[[], DBAdapter],
        table: str,
        output_path: str,
        reimport: bool,
    ) -> None:
        logger = self._make_logger(job_id)
        try:
            db_conn = db_conn_factory()
            try:
                cols, rows = imo_vmdb.export_table(db_conn, table, reimport=reimport)
                out = io.StringIO()
                writer = csv.writer(out, delimiter=";")
                writer.writerow(cols)
                writer.writerows(rows)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(out.getvalue())
                logger.info(
                    "Exported %d rows from '%s' to %s", len(rows), table, output_path
                )
                exit_code = 0
            except Exception as exc:
                logger.error("Export failed: %s", exc)
                exit_code = 1
            finally:
                db_conn.close()
        except Exception as exc:
            logger.critical("Unexpected error: %s", exc)
            exit_code = 100
        self._finish_job(job_id, exit_code)

    def _start(self, target: Callable[..., Any], *args: Any) -> str | None:
        job_id = self._allocate_job()
        if job_id is None:
            return None
        t = threading.Thread(target=target, args=(job_id,) + args, daemon=True)
        t.start()
        return job_id

    def start_initdb(self, db_conn_factory: Callable[[], DBAdapter]) -> str | None:
        """Start a database initialisation job.

        :param db_conn_factory: Callable returning a new database connection.
        :return: Job ID string, or ``None`` if another job is already running.
        """
        return self._start(self._run_simple, imo_vmdb.initdb, db_conn_factory)

    def start_normalize(self, db_conn_factory: Callable[[], DBAdapter]) -> str | None:
        """Start a normalisation job.

        :param db_conn_factory: Callable returning a new database connection.
        :return: Job ID string, or ``None`` if another job is already running.
        """
        return self._start(self._run_simple, imo_vmdb.normalize, db_conn_factory)

    def start_cleanup(self, db_conn_factory: Callable[[], DBAdapter]) -> str | None:
        """Start a cleanup job.

        :param db_conn_factory: Callable returning a new database connection.
        :return: Job ID string, or ``None`` if another job is already running.
        """
        return self._start(self._run_simple, imo_vmdb.cleanup, db_conn_factory)

    def start_import(
        self,
        db_conn_factory: Callable[[], DBAdapter],
        file_paths: list[str],
        *,
        do_delete: bool = False,
        is_permissive: bool = False,
        try_repair: bool = False,
    ) -> str | None:
        """Start a CSV import job.

        :param db_conn_factory: Callable returning a new database connection.
        :param file_paths: List of paths to CSV files to import.
            The files are deleted after the job completes.
        :param do_delete: Delete existing records before importing.
        :param is_permissive: Accept non-critical data errors.
        :param try_repair: Attempt automatic repair of malformed records.
        :return: Job ID string, or ``None`` if another job is already running.
        """
        return self._start(
            self._run_import,
            db_conn_factory,
            file_paths,
            do_delete,
            is_permissive,
            try_repair,
        )

    def start_export(
        self,
        db_conn_factory: Callable[[], DBAdapter],
        table: str,
        output_path: str,
        *,
        reimport: bool = False,
    ) -> str | None:
        """Start a CSV export job.

        :param db_conn_factory: Callable returning a new database connection.
        :param table: Table name to export (see :func:`imo_vmdb.export_table`).
        :param output_path: Path where the CSV file (``;``-separated) will be written.
        :param reimport: If ``True``, export in reimport-compatible format.
        :return: Job ID string, or ``None`` if another job is already running.
        """
        return self._start(
            self._run_export, db_conn_factory, table, output_path, reimport
        )

    def get_status(self, job_id: str) -> dict | None:
        """Return the current status of a job.

        :param job_id: Job ID returned by a ``start_*`` method.
        :return: Dict with keys ``running`` (bool) and ``exit_code`` (int or
            ``None`` while running), or ``None`` if the job ID is unknown.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return {"running": job["running"], "exit_code": job["exit_code"]}

    def iter_logs(self, job_id: str) -> Iterator[str] | None:
        """Return a blocking iterator over log lines for a job.

        Iterating blocks until the next log line is available and stops when
        the job finishes. Returns ``None`` if the job ID is unknown.

        When used in an HTTP handler, consume this iterator in a background
        thread or a streaming response to avoid blocking the request worker.

        :param job_id: Job ID returned by a ``start_*`` method.
        :return: Iterator of log line strings, or ``None`` if unknown.
        """
        if job_id not in self._jobs:
            return None
        return self._iter_logs_impl(job_id)

    def _iter_logs_impl(self, job_id: str) -> Iterator[str]:
        q = self._jobs[job_id]["queue"]
        while True:
            line = q.get()
            if line is None:
                return
            yield line
