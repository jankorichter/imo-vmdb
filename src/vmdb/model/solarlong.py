import datetime
import numpy as np
import warnings
from astropy.coordinates import solar_system_ephemeris, get_body, EarthLocation
from astropy.coordinates import BarycentricTrueEcliptic
from astropy.time import Time as AstropyTime


class Solarlong(object):

    def __init__(self, db_conn):
        self.days = {}
        self.loc = EarthLocation(
            lat=0.0,
            lon=0.0,
            height=0
        )
        self.load(db_conn)

    def calculate(self, time):
        time = AstropyTime(time)
        with solar_system_ephemeris.set('builtin'):
            earth_pos = get_body('earth', time, self.loc)
            earth_pos = earth_pos.transform_to(BarycentricTrueEcliptic)
            sl = earth_pos.lon.degree + 180.0

            return np.where(sl > 360.0, sl - 360.0, sl)

    def get(self, time):
        t0 = datetime.datetime(time.year, time.month, time.day, 0, 0, 0)
        t1 = t0 + datetime.timedelta(days=1)

        t0f = t0.strftime("%Y-%m-%d")
        if t0f not in self.days:
            self.days[t0f] = self.calculate((t0,))[0]

        t1f = t1.strftime("%Y-%m-%d")
        if t1f not in self.days:
            self.days[t1f] = self.calculate((t1,))[0]

        sl0 = self.days[t0f]
        sl1 = self.days[t1f]
        if sl0 > sl1:
            sl1 += 360.0

        sl = (sl1 - sl0) * ((time - t0) / (t1 - t0)) + sl0
        if sl > 360.0:
            return sl - 360

        return sl

    def load(self, db_conn):
        cur = db_conn.cursor()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            cur.execute(db_conn.convert_stmt('''
                CREATE TABLE IF NOT EXISTS solarlong_lookup (
                    date DATE NOT NULL,
                    sl double precision NOT NULL,
                    CONSTRAINT solarlong_lookup_pkey PRIMARY KEY (date)
                )'''
            ))

        cur.execute(db_conn.convert_stmt('''SELECT date, sl FROM solarlong_lookup'''))
        column_names = [desc[0] for desc in cur.description]
        for record in cur:
            record = dict(zip(column_names, record))
            rdate = record['date']
            if not isinstance(rdate, str):
                rdate = rdate.strftime("%Y-%m-%d")
            self.days[rdate] = record['sl']

        cur.close()
