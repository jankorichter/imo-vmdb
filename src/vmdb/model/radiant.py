import math
from astropy.time import Time as AstropyTime
from astropy import units as u


class Position(object):

    def __init__(self, ra, dec):
        self.ra = ra
        self.dec = dec

    def get_altitude(self, loc, time):
        obstime = AstropyTime(time, format='datetime', scale='utc')
        sidtime = obstime.sidereal_time('mean', longitude=loc.long * u.deg).rad
        rad_alt = math.cos(math.radians(loc.lat))
        rad_alt *= math.cos(math.radians(self.dec))
        rad_alt *= math.cos(sidtime - math.radians(self.ra))
        rad_alt += math.sin(math.radians(loc.lat)) * math.sin(math.radians(self.dec))

        return math.degrees(math.asin(rad_alt))


class Drift(object):

    def __init__(self, positions):
        self._positions = positions

    def get_position(self, time):
        positions = self._positions
        if len(positions) == 1:
            p = positions[0]
            return p['pos']

        yday = time.timetuple().tm_yday
        left = {'yday': -1, 'invalid': None}
        right = {'yday': 400, 'invalid': None}

        for pos in positions:
            diff = pos['yday'] - yday
            left_diff = yday - left['yday']
            right_diff = right['yday'] - yday

            if diff <= 0 and left_diff > -diff:
                left = pos
            if 0 <= diff < right_diff:
                right = pos

        if 'invalid' in left or 'invalid' in right:
            return None

        left_yday = left['yday']
        left_pos = left['pos']
        right_yday = right['yday']
        right_pos = right['pos']

        if yday == left_yday:
            return left_pos

        if yday == right_yday:
            return right_pos

        if right_pos.ra < left_pos.ra:
            right_pos.ra += 360.0

        f = float(yday - left_yday) / float(right_yday - left_yday)
        ra = f * (right_pos.ra - left_pos.ra) + left_pos.ra
        dec = f * (right_pos.dec - left_pos.dec) + left_pos.dec

        if right_pos.ra >= 360.0:
            right_pos.ra -= 360.0

        if ra >= 360.0:
            ra -= 360.0

        pos = Position(ra, dec)
        self._positions.append({'yday': yday, 'pos': pos})

        return pos


class Storage(object):

    def __init__(self, conn):
        self._conn = conn

    @staticmethod
    def _get_ydays():
        month_lengths = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30]
        ydays = []  # day of the year per month
        last = 0

        for i in month_lengths:
            last += i
            ydays.append(last)

        return ydays

    def load(self):
        ydays = self._get_ydays()
        radiants = {}
        cur = self._conn.cursor()
        cur.execute('SELECT * FROM imported_radiant ORDER BY shower, month, day')
        column_names = [desc[0] for desc in cur.description]
        for r in cur:
            r = dict(zip(column_names, r))
            iau_code = r['shower']
            if iau_code not in radiants:
                radiants[iau_code] = []

            radiants[iau_code].append({
                'yday': ydays[r['month'] - 1] + r['day'],
                'pos': Position(r['ra'], r['dec'])
            })

        cur.close()

        return dict((rad[0], Drift(rad[1])) for rad in radiants.items())
