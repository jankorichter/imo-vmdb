import math
from astropy.time import Time as AstropyTime
from astropy import units as u


class Location(object):

    def __init__(self, long, lat):
        self.long = long
        self.lat = lat

    def get_radiant_alt(self, time, radiant):
        obstime = AstropyTime(time, format='datetime', scale='utc')
        sidtime = obstime.sidereal_time('mean', longitude=self.long * u.deg).rad
        rad_alt = math.cos(math.radians(self.lat))
        rad_alt *= math.cos(math.radians(radiant.dec))
        rad_alt *= math.cos(sidtime - math.radians(radiant.ra))
        rad_alt += math.sin(math.radians(self.lat)) * math.sin(math.radians(radiant.dec))

        return math.degrees(math.asin(rad_alt))


class Rate(object):

    def __init__(self, conn, solarlongs, showers):
        self._conn = conn
        self._solarlongs = solarlongs
        self._showers = showers

    def __call__(self, drop_tables, process_count, mod):
        solarlongs = self._solarlongs
        cur = self._conn.cursor()
        cur.execute('''
            SELECT
                r.id,
                s.observer_id,
                s.longitude,
                s.latitude,
                s.elevation,
                r.shower,
                r.session_id,
                r.user_id,
                r."start",
                r."end",
                r.t_eff,
                r.f,
                r.lm,
                r."number" AS freq
            FROM imported_rate as r
            INNER JOIN imported_session as s ON s.id = r.session_id
            WHERE
                r."start" < r."end" AND
                r.id %% %s = %s
        ''', (process_count, mod))

        column_names = [desc[0] for desc in cur.description]
        rate_stmt = '''
            INSERT INTO rate (
                id,
                shower,
                period_start,
                period_end,
                sl_start,
                sl_end,
                session_id,
                observer_id,
                freq,
                lim_mag,
                t_eff,
                f,
                t_zenith,
                rad_alt
            ) VALUES (
                %(rate_id)s,
                %(shower)s,
                %(period_start)s,
                %(period_end)s,
                %(sl_start)s,
                %(sl_end)s,
                %(session_id)s,
                %(observer_id)s,
                %(freq)s,
                %(lim_mag)s,
                %(t_eff)s,
                %(f)s,
                %(t_zenith)s,
                %(rad_alt)s
            )
        '''

        write_cur = self._conn.cursor()
        for record in cur:
            record = dict(zip(column_names, record))

            if not drop_tables:
                write_cur.execute('DELETE FROM rate WHERE id = %s', (record['id'],))

            t_abs = record['end'] - record['start']
            t_mean = record['start'] + t_abs / 2
            sl_start = solarlongs.get(record['start'])
            sl_end = solarlongs.get(record['end'])
            iau_code = record['shower']

            rad_alt = None
            t_zenith = None
            shower = self._showers[iau_code] if iau_code in self._showers else None
            radiant = shower.get_radiant(t_mean) if shower is not None else None

            if radiant is not None:
                loc = Location(record['longitude'], record['latitude'])
                rad_alt = loc.get_radiant_alt(t_mean, radiant)
                z = math.sqrt(125 + shower.v * shower.v)
                t_zenith = record['t_eff'] * (z + shower.v * (math.sin(math.radians(rad_alt)) - 1)) / z
                t_zenith /= float(record['f'])

            rate = {
                'shower': iau_code,
                'period_start': record['start'],
                'period_end': record['end'],
                'sl_start': sl_start,
                'sl_end': sl_end,
                'rate_id': record['id'],
                'session_id': record['session_id'],
                'observer_id': record['user_id'],
                'freq': record['freq'],
                'lim_mag': record['lm'],
                't_eff': record['t_eff'],
                'f': record['f'],
                't_zenith': t_zenith,
                'rad_alt': rad_alt
            }
            write_cur.execute(rate_stmt, rate)

        cur.close()
        write_cur.close()
