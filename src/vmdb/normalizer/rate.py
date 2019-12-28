import math
import sys
from astropy.time import Time as AstropyTime
from astropy import units as u


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

            if record['user_id'] != record['observer_id']:
                print(
                    'WARN in ' + record['id'] + ' : user_id ' + record['user_id'] + ' != observer_id ' + record[
                        'observer_id'],
                    file=sys.stderr
                )

            t_abs = record['end'] - record['start']
            t_mean = record['start'] + t_abs / 2
            sl_start = solarlongs.get(record['start'])
            sl_end = solarlongs.get(record['end'])
            iau_code = record['shower']
            iau_code = None if iau_code == 'SPO' else iau_code

            rad_alt = None
            t_zenith = None
            shower = self._showers[iau_code] if iau_code in self._showers else None
            radiant = shower.get_radiant(t_mean) if shower is not None else None

            if radiant is not None:
                obstime = AstropyTime(t_mean, format='datetime', scale='utc')
                loc = (math.radians(record['longitude']), math.radians(record['latitude']))
                sidtime = obstime.sidereal_time('mean', longitude=loc[0] * u.rad).rad
                radiant = (math.radians(radiant.ra), math.radians(radiant.dec))
                rad_alt = math.sin(loc[1]) * math.sin(radiant[1])
                rad_alt += math.cos(loc[1]) * math.cos(radiant[1]) * math.cos(sidtime - radiant[0])
                z = math.sqrt(125 + shower.v * shower.v)
                t_zenith = record['t_eff'] * (z + shower.v * (rad_alt - 1)) / z
                t_zenith /= float(record['f'])
                rad_alt = math.degrees(math.asin(rad_alt))

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
