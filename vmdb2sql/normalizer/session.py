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

        cur.execute(self._insert_stmt, rate)


class SessionNormalizer(BaseNormalizer):

    def __init__(self, db_conn, logger, drop_tables):
        super().__init__(db_conn, logger, drop_tables)
        Record.init_stmt(db_conn)

    def run(self):
        db_conn = self.db_conn
        cur = db_conn.cursor()

        if self.drop_tables:
            cur.execute(db_conn.convert_stmt('''
                SELECT count(*) FROM imported_session
            '''))
            self.counter_read = cur.fetchone()[0]
            cur.execute(db_conn.convert_stmt('''
                INSERT INTO obs_session SELECT * FROM imported_session
            '''))
            cur.execute(db_conn.convert_stmt('''
                SELECT count(*) FROM obs_session
            '''))
            self.counter_write = cur.fetchone()[0]
            cur.close()
            return

        cur.execute(db_conn.convert_stmt('''
            SELECT
                id,
                observer_id,
                latitude,
                longitude,
                elevation
            FROM imported_session
        '''))

        column_names = [desc[0] for desc in cur.description]
        write_cur = db_conn.cursor()
        delete_stmt = db_conn.convert_stmt('DELETE FROM obs_session WHERE id = %(id)s')
        for _record in cur:
            self.counter_read += 1
            record = Record(dict(zip(column_names, _record)))
            write_cur.execute(delete_stmt, {'id': record.id})
            record.write(write_cur)
            self.counter_write += 1

        cur.close()
        write_cur.close()
