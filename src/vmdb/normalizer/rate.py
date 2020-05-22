import math
import warnings
from vmdb.model.location import Location


class Record(object):
    insert_stmt = '''
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
            rad_alt,
            rad_corr
        ) VALUES (
            %(id)s,
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
            %(rad_alt)s,
            %(rad_corr)s
        )
    '''

    def __init__(self, record):
        self.id = record['id']
        self.shower = record['shower']
        self.session_id = record['session_id']
        self.user_id = record['user_id']
        self.start = record['start']
        self.end = record['end']
        self.freq = record['freq']
        self.lm = record['lm']
        self.t_eff = record['t_eff']
        self.f = record['f']
        self.loc = Location(record['longitude'], record['latitude'])

    def __eq__(self, other):
        return not self != other

    def __ne__(self, other):
        if self.session_id != other.session_id:
            return True

        if self.shower != other.shower:
            return True

        if self.end <= other.start:
            return True

        if self.start >= other.end:
            return True

        return False

    def __contains__(self, other):
        if self != other:
            return False

        if self.start > other.start or self.end < other.end:
            return False

        return True

    def write(self, cur, solarlongs, showers):
        t_abs = self.end - self.start
        t_mean = self.start + t_abs / 2
        sl_start = solarlongs.get(self.start)
        sl_end = solarlongs.get(self.end)
        iau_code = self.shower

        rad_alt = None
        rad_corr = None
        shower = showers[iau_code] if iau_code in showers else None
        radiant = shower.get_radiant(t_mean) if shower is not None else None

        if radiant is not None:
            rad_alt = radiant.get_altitude(self.loc, t_mean)
            z = math.sqrt(125 + shower.v * shower.v)
            rad_corr = z / (z + shower.v * (math.sin(math.radians(rad_alt)) - 1))

        rate = {
            'id': self.id,
            'shower': iau_code,
            'period_start': self.start,
            'period_end': self.end,
            'sl_start': sl_start,
            'sl_end': sl_end,
            'session_id': self.session_id,
            'observer_id': self.user_id,
            'freq': self.freq,
            'lim_mag': self.lm,
            't_eff': self.t_eff,
            'f': self.f,
            'rad_alt': rad_alt,
            'rad_corr': rad_corr
        }

        cur.execute(self.insert_stmt, rate)


class Normalizer(object):

    def __init__(self, conn, solarlongs, showers):
        self._conn = conn
        self._solarlongs = solarlongs
        self._showers = showers

    def __call__(self, drop_tables, divisor, mod):
        solarlongs = self._solarlongs
        showers = self._showers
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
                r.session_id %% %s = %s
            ORDER BY
                r.session_id ASC,
                r.shower ASC,
                r."start" ASC,
                r."end" DESC
        ''', (divisor, mod))

        column_names = [desc[0] for desc in cur.description]
        write_cur = self._conn.cursor()
        prev_record = None
        for _record in cur:
            record = Record(dict(zip(column_names, _record)))
            if not drop_tables:
                write_cur.execute('DELETE FROM rate WHERE id = %s', (record.id,))

            if prev_record is None:
                prev_record = record
                continue

            if record in prev_record:
                msg = "Rate observation %s contains observation %s. Observation %s discarded."
                warnings.warn(msg % (prev_record.id, record.id, prev_record.id))
                prev_record = record
                continue

            if prev_record == record:
                msg = "Rate observation %s overlaps observation %s. Observation %s discarded."
                warnings.warn(msg % (prev_record.id, record.id, record.id))
                continue

            prev_record.write(write_cur, solarlongs, showers)
            prev_record = record

        if prev_record is not None:
            prev_record.write(write_cur, solarlongs, showers)

        cur.close()
        write_cur.close()
