import json
import math

from imo_vmdb.db import DBException
from imo_vmdb.normalizer import BaseNormalizer, BaseRecord


class Record(BaseRecord):
    """A single magnitude observation with its per-magnitude counts.

    Extends :class:`~imo_vmdb.normalizer.BaseRecord` with the JSON-encoded
    magnitude distribution and the :meth:`write` method that computes the
    mean magnitude and inserts both the summary and detail rows.

    :param record: Dict of columns from the import query.
    """

    _insert_stmt = """
        INSERT INTO magnitude (
            id,
            shower,
            period_start,
            period_end,
            sl_start,
            sl_end,
            session_id,
            freq,
            mean
        ) VALUES (
            %(id)s,
            %(shower)s,
            %(period_start)s,
            %(period_end)s,
            %(sl_start)s,
            %(sl_end)s,
            %(session_id)s,
            %(freq)s,
            %(mean)s
        )
    """

    _insert_detail_stmt = """
        INSERT INTO magnitude_detail (
            id,
            magn,
            freq
        ) VALUES (
            %(id)s,
            %(magn)s,
            %(freq)s
        )
    """

    def __init__(self, record):
        super().__init__(record)
        self.magn = json.loads(record["magn"])

    @classmethod
    def init_stmt(cls, db_conn):
        """Compile INSERT statements for the current database dialect.

        :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
        """
        cls._insert_stmt = db_conn._convert_stmt(cls._insert_stmt)
        cls._insert_detail_stmt = db_conn._convert_stmt(cls._insert_detail_stmt)

    def write(self, cur, sky):
        """Compute the mean magnitude and insert rows into ``magnitude`` and ``magnitude_detail``.

        :param cur: Open database cursor.
        :param sky: :class:`~imo_vmdb.model.sky.Sky` instance for solar longitude.
        :raises DBException: On database error.
        """
        mid = self.id
        freq = int(sum(m for m in self.magn.values()))
        magn_items = self.magn.items()
        mean = sum(float(m) * float(n) for m, n in magn_items) / freq
        sl_start = sky.solarlong(self.start)
        sl_end = sky.solarlong(self.end)
        iau_code = self.shower
        magn = {
            "id": mid,
            "shower": iau_code,
            "period_start": self.start,
            "period_end": self.end,
            "sl_start": math.degrees(sl_start),
            "sl_end": math.degrees(sl_end),
            "session_id": self.session_id,
            "freq": freq,
            "mean": mean,
        }

        try:
            cur.execute(self._insert_stmt, magn)
        except Exception as e:
            raise DBException(str(e))

        for m, n in magn_items:
            magn = {
                "id": mid,
                "magn": int(m),
                "freq": float(n),
            }
            try:
                cur.execute(self._insert_detail_stmt, magn)
            except Exception as e:
                raise DBException(str(e))


class MagnitudeNormalizer(BaseNormalizer):
    """Normalises magnitude observations from ``imported_magnitude`` into ``magnitude``.

    Reads records joined to ``obs_session``, discards observations with
    mismatched observer IDs or overlapping time periods, and writes the
    remainder with computed solar longitude and mean magnitude.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :param logger: Logger for error messages.
    :param sky: :class:`~imo_vmdb.model.sky.Sky` instance for solar longitude.
    """

    def __init__(self, db_conn, logger, sky):
        super().__init__(db_conn, logger)
        self._sky = sky
        Record.init_stmt(db_conn)

    def run(self):
        """Execute the magnitude normalisation pass.

        :raises DBException: On database error.
        """
        db_conn = self._db_conn
        try:
            cur = db_conn.cursor()
            cur.execute(
                db_conn._convert_stmt("""
                SELECT
                    m.id,
                    s.longitude,
                    s.latitude,
                    s.elevation,
                    s.observer_id AS "session_observer_id",
                    m.shower,
                    m.session_id,
                    m.observer_id,
                    m."start",
                    m."end",
                    m.magn
                FROM imported_magnitude as m
                INNER JOIN obs_session as s ON s.id = m.session_id
                ORDER BY
                    m.session_id ASC,
                    m.shower ASC,
                    m."start" ASC,
                    m."end" DESC
            """)
            )
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]

        try:
            write_cur = db_conn.cursor()
        except Exception as e:
            raise DBException(str(e))

        prev_record = None
        delete_stmt = db_conn._convert_stmt("DELETE FROM magnitude WHERE id = %(id)s")
        for _record in cur:
            self.counter_read += 1

            record = Record(dict(zip(column_names, _record, strict=False)))
            if record.observer_id != record.session_observer_id:
                self._log_discard(
                    record.session_id,
                    record.id,
                    "observer ID differs from session observer ID",
                )
                prev_record = record
                continue

            try:
                write_cur.execute(delete_stmt, {"id": record.id})
            except Exception as e:
                raise DBException(str(e))

            if prev_record is None:
                prev_record = record
                continue

            if record in prev_record:
                self._log_discard(
                    prev_record.session_id,
                    prev_record.id,
                    "time period contained by observation %s" % record.id,
                )
                prev_record = record
                continue

            if prev_record == record:
                self._log_discard(
                    record.session_id,
                    record.id,
                    "time period overlaps observation %s" % prev_record.id,
                )
                continue

            try:
                prev_record.write(write_cur, self._sky)
            except DBException as err:
                self._log_discard(prev_record.session_id, prev_record.id, str(err))
                prev_record = record
                continue
            self.counter_write += 1
            prev_record = record

        if prev_record is not None:
            try:
                prev_record.write(write_cur, self._sky)
                self.counter_write += 1
            except DBException as err:
                self._log_discard(prev_record.session_id, prev_record.id, str(err))

        try:
            cur.close()
            write_cur.close()
        except Exception as e:
            raise DBException(str(e))
