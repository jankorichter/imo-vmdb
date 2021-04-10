import datetime
from imo_vmdb.db import DBException
from imo_vmdb.model.radiant import Position


class Shower(object):

    def __init__(self, record, drift):
        self._drift = drift
        self.id = record['id']
        self.iau_code = record['iau_code']
        self.name = record['name']
        self.start_month = record['start_month']
        self.start_day = record['start_day']
        self.end_month = record['end_month']
        self.end_day = record['end_day']
        self.peak_month = record['peak_month']
        self.peak_day = record['peak_day']
        self.v = record['v']
        self.r = record['r']
        self.zhr = record['zhr']
        self.position = None

        if record['ra'] is not None and record['dec'] is not None:
            self.position = Position(record['ra'], record['dec'])

    def get_radiant(self, time):
        year = time.year
        start = datetime.datetime(year, self.start_month, self.start_day, 0, 0, 0)
        end = datetime.datetime(year, self.end_month, self.end_day, 23, 59, 59)

        if start > end and start > time > end:
            return None

        if start < end and (time < start or time > end):
            return None

        if self._drift is None:
            return self.position

        return self._drift.get_position(time)


class Storage(object):

    def __init__(self, db_conn):
        self._db_conn = db_conn

    def load(self, radiants):
        try:
            cur = self._db_conn.cursor()
            cur.execute('SELECT * FROM shower')
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]
        showers = {}
        for record in cur:
            record = dict(zip(column_names, record))
            iau_code = record['iau_code']
            showers[iau_code] = Shower(record, radiants[iau_code] if iau_code in radiants else None)

        try:
            cur.close()
        except Exception as e:
            raise DBException(str(e))

        return showers
