from imo_vmdb.db import DBException
from imo_vmdb.normalizer import BaseNormalizer


class Record:
    """An observation session record ready to be written to ``obs_session``.

    :param record: Dict of columns from the import query.
    """

    _insert_stmt = """
        INSERT INTO obs_session (
            id,
            latitude,
            longitude,
            elevation,
            observer_id,
            observer_name,
            country,
            city
        ) VALUES (
            %(id)s,
            %(latitude)s,
            %(longitude)s,
            %(elevation)s,
            %(observer_id)s,
            %(observer_name)s,
            %(country)s,
            %(city)s
        )
    """

    def __init__(self, record):
        self.id = record["id"]
        self.latitude = record["latitude"]
        self.longitude = record["longitude"]
        self.elevation = record["elevation"]
        self.observer_id = record["observer_id"]
        self.observer_name = record["observer_name"]
        self.country = record["country"]
        self.city = record["city"]

    @classmethod
    def init_stmt(cls, db_conn):
        """Compile the INSERT statement for the current database dialect.

        :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
        """
        cls._insert_stmt = db_conn._convert_stmt(cls._insert_stmt)

    def write(self, cur):
        """Insert this record into ``obs_session`` using *cur*.

        :param cur: Open database cursor.
        :raises DBException: On database error.
        """
        rate = {
            "id": self.id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "observer_id": self.observer_id,
            "observer_name": self.observer_name,
            "country": self.country,
            "city": self.city,
        }
        try:
            cur.execute(self._insert_stmt, rate)
        except Exception as e:
            raise DBException(str(e))


class SessionNormalizer(BaseNormalizer):
    """Copies rows from ``imported_session`` into ``obs_session``.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :param logger: Logger for error messages.
    """

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        Record.init_stmt(db_conn)

    def run(self):
        """Execute the session normalisation pass.

        Reads all rows from ``imported_session`` and upserts them into
        ``obs_session`` (delete-then-insert by primary key).

        :raises DBException: On database error.
        """
        db_conn = self._db_conn

        try:
            cur = db_conn.cursor()
            cur.execute(
                db_conn._convert_stmt("""
                SELECT
                    id,
                    latitude,
                    longitude,
                    elevation,
                    observer_id,
                    observer_name,
                    country,
                    city
                FROM imported_session
            """)
            )
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]

        try:
            write_cur = db_conn.cursor()
        except Exception as e:
            raise DBException(str(e))

        delete_stmt = db_conn._convert_stmt("DELETE FROM obs_session WHERE id = %(id)s")
        for _record in cur:
            self.counter_read += 1
            record = Record(dict(zip(column_names, _record, strict=False)))
            try:
                write_cur.execute(delete_stmt, {"id": record.id})
            except Exception as e:
                raise DBException(str(e))
            record.write(write_cur)
            self.counter_write += 1

        cur.close()
        write_cur.close()
