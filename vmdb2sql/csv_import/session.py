from vmdb2sql.csv_import import CsvParser, ImportException
from vmdb2sql.db import DBException


class SessionParser(CsvParser):

    _required_columns = {
        'session id',
        'observer id',
        'latitude',
        'longitude',
        'elevation'
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._init_logger('session import')
        self._insert_stmt = self._db_conn.convert_stmt('''
            INSERT INTO imported_session (
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
        ''')

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn.convert_stmt('DELETE FROM imported_session'))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        row = dict(zip(self.column_names, row))

        try:
            session_id = self._parse_session_id(row['session id'])
            observer_id = self._parse_observer_id(row['observer id'], 'observer id', session_id)
            lat = self._parse_latitude(row['latitude'], session_id)
            long = self._parse_longitude(row['longitude'], session_id)
            elevation = self._parse_elevation(row['longitude'], session_id)
        except ImportException as err:
            self._log_error(str(err))
            return False

        record = {
            'id': session_id,
            'observer_id': observer_id,
            'latitude': lat,
            'longitude': long,
            'elevation': elevation
        }

        try:
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_session_id(value):
        session_id = value.strip()
        if '' == session_id:
            raise ImportException("Session found without a session id.")

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException("id %s: invalid session id." % session_id)
        if session_id < 1:
            raise ImportException("id %s: session id must be greater than 0." % session_id)

        return session_id

    @staticmethod
    def _parse_latitude(value, session_id):
        lat = value.strip()
        if '' == lat:
            raise ImportException("id %s: latitude must not be empty." % session_id)

        try:
            lat = float(lat)
        except ValueError:
            raise ImportException("id %s: invalid latitude value. The value is %s." % (session_id, lat))

        if lat < -90 or lat > 90:
            raise ImportException("id %s: latitude must be between -90 and 90 instead of %s." % (session_id, lat))

        return lat

    @staticmethod
    def _parse_longitude(value, session_id):
        long = value.strip()
        if '' == long:
            raise ImportException("id %s: longitude must not be empty." % session_id)

        try:
            long = float(long)
        except ValueError:
            raise ImportException("id %s: invalid longitude value. The value is %s." % (session_id, long))

        if long < -180 or long > 180:
            raise ImportException("id %s: longitude must be between -180 and 180 instead of %s." % (session_id, long))

        return long

    def _parse_elevation(self, value, session_id):
        elevation = value.strip()
        if '' == elevation:
            if self._is_permissive:
                return None
            else:
                raise ImportException("id %s: elevation must not be empty." % session_id)

        try:
            elevation = float(elevation)
        except ValueError:
            raise ImportException("id %s: invalid elevation value. The value is %s." % (session_id, elevation))

        return elevation