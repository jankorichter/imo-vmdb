from vmdb2sql.db import DBException
from vmdb2sql.normalizer import BaseNormalizer


class Record(object):
    _insert_stmt = '''
        INSERT INTO obs_session (
            id,
            observer_id,
            latitude,
            longitude,
            elevation
        ) VALUES (
            %(id)s,
            %(observer_id)s,
            %(latitude)s,
            %(longitude)s,
            %(elevation)s
        )
    '''

    def __init__(self, record):
        self.id = record['id']
        self.observer_id = record['observer_id']
        self.latitude = record['latitude']
        self.longitude = record['longitude']
        self.elevation = record['elevation']

    @classmethod
    def init_stmt(cls, db_conn):
        cls._insert_stmt = db_conn.convert_stmt(cls._insert_stmt)

    def write(self, cur):

        rate = {
            'id': self.id,
            'observer_id': self.observer_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'elevation': self.elevation
        }
        try:
            cur.execute(self._insert_stmt, rate)
        except Exception as e:
            raise DBException(str(e))


class SessionNormalizer(BaseNormalizer):

    def __init__(self, db_conn, logger):
        super().__init__(db_conn, logger)
        Record.init_stmt(db_conn)

    def run(self):
        db_conn = self._db_conn
        
        try:
            cur = db_conn.cursor()
            cur.execute(db_conn.convert_stmt('''
                SELECT
                    id,
                    observer_id,
                    latitude,
                    longitude,
                    elevation
                FROM imported_session
            '''))
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]
        
        try:
            write_cur = db_conn.cursor()
        except Exception as e:
            raise DBException(str(e))

        delete_stmt = db_conn.convert_stmt('DELETE FROM obs_session WHERE id = %(id)s')
        for _record in cur:
            self.counter_read += 1
            record = Record(dict(zip(column_names, _record)))
            try:
                write_cur.execute(delete_stmt, {'id': record.id})
            except Exception as e:
                raise DBException(str(e))
            record.write(write_cur)
            self.counter_write += 1

        cur.close()
        write_cur.close()
