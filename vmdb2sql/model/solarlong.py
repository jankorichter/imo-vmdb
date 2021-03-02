import numpy as np
from astropy.coordinates import solar_system_ephemeris, get_body, EarthLocation
from astropy.coordinates import BarycentricTrueEcliptic
from astropy.time import Time as AstropyTime
from datetime import date, datetime, time, timedelta
from vmdb2sql.db import DBException


class Solarlong(object):

    _loc = EarthLocation(
        lat=0.0,
        lon=0.0,
        height=0
    )

    def __init__(self):
        self._days = {}

    def get(self, t):
        t0 = datetime(t.year, t.month, t.day, 0, 0, 0)
        t1 = t0 + timedelta(days=1)

        t0f = t0.strftime("%Y-%m-%d")
        if t0f not in self._days:
            self._days[t0f] = self._calculate((t0,))[0]

        t1f = t1.strftime("%Y-%m-%d")
        if t1f not in self._days:
            self._days[t1f] = self._calculate((t1,))[0]

        sl0 = self._days[t0f]
        sl1 = self._days[t1f]
        if sl0 > sl1:
            sl1 += 360.0

        sl = (sl1 - sl0) * ((t - t0) / (t1 - t0)) + sl0
        if sl > 360.0:
            return sl - 360

        return sl

    def load(self, db_conn):
        try:
            cur = db_conn.cursor()
        except Exception as e:
            raise DBException(str(e))

        self._refresh(db_conn, cur)

        try:
            cur.execute(db_conn.convert_stmt('SELECT date, sl FROM solarlong_lookup'))
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]
        for record in cur:
            record = dict(zip(column_names, record))
            rdate = record['date']
            if not isinstance(rdate, str):
                rdate = rdate.strftime("%Y-%m-%d")
            self._days[rdate] = record['sl']

        try:
            cur.close()
        except Exception as e:
            raise DBException(str(e))

    @classmethod
    def _refresh(cls, db_conn, cur):
        diff = timedelta(days=1)
        insert_stmt = db_conn.convert_stmt(
            '''
                INSERT INTO solarlong_lookup (
                    date,
                    sl
                ) VALUES (
                    %(date)s,
                    %(sl)s
                )
            '''
        )
        date_gen = cls._date_generator(
            cls._get_max_date(db_conn, cur),
            datetime.utcnow() + timedelta(days=1),
            diff
        )

        for time_list in date_gen:
            sl_list = cls._calculate(time_list)

            for z in zip(time_list, sl_list):
                record = {
                    'date': z[0].strftime("%Y-%m-%d"),
                    'sl': float(z[1]),
                }
                try:
                    cur.execute(insert_stmt, record)
                except Exception as e:
                    raise DBException(str(e))

    @classmethod
    def _calculate(cls, t):
        t = AstropyTime(t)
        with solar_system_ephemeris.set('builtin'):
            earth_pos = get_body('earth', t, cls._loc)
            earth_pos = earth_pos.transform_to(BarycentricTrueEcliptic)
            sl = earth_pos.lon.degree + 180.0

            return np.where(sl > 360.0, sl - 360.0, sl)

    @staticmethod
    def _get_max_date(db_conn, cur):
        try:
            cur.execute(db_conn.convert_stmt(
                'SELECT max(date) FROM solarlong_lookup'
            ))
        except Exception as e:
            raise DBException(str(e))

        rdate = cur.fetchone()[0]
        if rdate is None:
            return datetime(1980, 1, 1, 0, 0, 0)

        if isinstance(rdate, str):
            rdate = date.fromisoformat(rdate)

        if isinstance(rdate, date):
            rdate = datetime.combine(rdate, time(0, 0, 0))

        return rdate + timedelta(days=1)

    @staticmethod
    def _date_generator(start_date, end_date, diff):
        i = 0
        data = []
        t = start_date
        while t <= end_date:
            data.append(t)

            if i > 1000:
                yield data
                i = 0
                data = []

            i += 1
            t = t + diff

        if len(data) > 0:
            yield data
