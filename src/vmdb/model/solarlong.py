import datetime
import numpy as np
from astropy.coordinates import solar_system_ephemeris, get_body, EarthLocation
from astropy.coordinates import BarycentricTrueEcliptic
from astropy.time import Time as AstropyTime


class Solarlong(object):

    def __init__(self, conn):
        self.days = {}
        self.loc = EarthLocation(
            lat=0.0,
            lon=0.0,
            height=0
        )
        self.load(conn)

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

    def load(self, conn):
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS imported_solarlong (
                date DATE NOT NULL,
                sl double precision NOT NULL,
                CONSTRAINT imported_solarlong_pkey PRIMARY KEY (date)
            )''')

        cur.execute('''SELECT date, sl FROM imported_solarlong''')
        column_names = [desc[0] for desc in cur.description]
        for record in cur:
            record = dict(zip(column_names, record))
            self.days[record['date'].strftime("%Y-%m-%d")] = record['sl']

        cur.close()
