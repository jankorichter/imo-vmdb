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
            t_zenith,
            rad_alt
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
            %(t_zenith)s,
            %(rad_alt)s
        )
    '''

    _insert_ref_stmt = '''
        INSERT INTO rate_ref (
            rate_id,
            id
        ) VALUES (
            %(rate_id)s,
            %(id)s
        )
    '''

    def __init__(self, record):
        self.is_valid = True
        self.ids = (record['id'],)
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
        if not self.is_valid or not other.is_valid:
            return False

        if self != other:
            return False

        if self.start > other.start or self.end < other.end:
            return False

        return self.freq == other.freq

    def __add__(self, other):
        if self != other:
            return None

        have_same_period = self.start == other.start and self.end == other.end
        if other in self and not have_same_period:
            # we discard here a probably already aggregated observation
            ids = ','.join(sorted(str(i) for i in self.ids))
            warnings.warn("Probably already aggregated rate observations (%s) found. Discarded." % (ids,))

            return other

        self.is_valid = self.is_valid and other.is_valid and have_same_period
        self.ids = self.ids + other.ids

        if not self.is_valid:
            self.start = min((self.start, other.start,))
            self.end = max((self.end, other.end,))

            return self

        return self

    def write(self, cur, solarlongs, showers):
        if not self.is_valid:
            ids = ','.join(sorted(str(i) for i in self.ids))
            warnings.warn("Overlapping rate observations found (%s). Discarded." % (ids,))

            return

        rid = min(self.ids)
        t_abs = self.end - self.start
        t_mean = self.start + t_abs / 2
        sl_start = solarlongs.get(self.start)
        sl_end = solarlongs.get(self.end)
        iau_code = self.shower

        rad_alt = None
        t_zenith = None
        shower = showers[iau_code] if iau_code in showers else None
        radiant = shower.get_radiant(t_mean) if shower is not None else None

        if radiant is not None:
            rad_alt = radiant.get_altitude(self.loc, t_mean)
            z = math.sqrt(125 + shower.v * shower.v)
            t_zenith = self.t_eff * (z + shower.v * (math.sin(math.radians(rad_alt)) - 1)) / z
            t_zenith /= float(self.f)

        rate = {
            'id': rid,
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
            't_zenith': t_zenith,
            'rad_alt': rad_alt
        }

        cur.execute(self.insert_stmt, rate)

        for rate_id in self.ids:
            ref = {
                'rate_id': rate_id,
                'id': rid,
            }
            cur.execute(self._insert_ref_stmt, ref)


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
                write_cur.execute('''
                    DELETE FROM rate WHERE id IN (
                        SELECT id FROM rate_ref WHERE rate_id = %s
                    )
                ''', (record.ids[0],))

            if prev_record is None:
                prev_record = record
                continue

            merged_record = prev_record + record
            if merged_record is not None:
                prev_record = merged_record
                continue

            prev_record.write(write_cur, solarlongs, showers)
            prev_record = record

        if prev_record is not None:
            prev_record.write(write_cur, solarlongs, showers)

        cur.close()
        write_cur.close()
