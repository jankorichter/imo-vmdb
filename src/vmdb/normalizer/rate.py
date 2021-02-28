import math
from datetime import datetime
from vmdb.normalizer import BaseNormalizer


class Location(object):

    def __init__(self, long, lat):
        self.long = long
        self.lat = lat


class Record(object):
    _insert_stmt = '''
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

        if isinstance(record['start'], datetime):
            self.start = record['start']
        else:
            self.start = datetime.strptime(record['start'], '%Y-%m-%d %H:%M:%S')

        if isinstance(record['end'], datetime):
            self.end = record['end']
        else:
            self.end = datetime.strptime(record['end'], '%Y-%m-%d %H:%M:%S')

        self.freq = record['freq']
        self.lm = record['lm']
        self.t_eff = record['t_eff']
        self.f = record['f']
        self.loc = Location(record['longitude'], record['latitude'])

    @classmethod
    def init_stmt(cls, db_conn):
        cls._insert_stmt = db_conn.convert_stmt(cls._insert_stmt)

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

        cur.execute(self._insert_stmt, rate)


class RateNormalizer(BaseNormalizer):

    def __init__(self, db_conn, logger, drop_tables, solarlongs, showers):
        super().__init__(db_conn, logger, drop_tables)
        self.solarlongs = solarlongs
        self.showers = showers
        Record.init_stmt(db_conn)

    def run(self):
        solarlongs = self.solarlongs
        showers = self.showers
        db_conn = self.db_conn
        cur = db_conn.cursor()
        cur.execute(db_conn.convert_stmt('''
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
            INNER JOIN obs_session as s ON s.id = r.session_id
            ORDER BY
                r.session_id ASC,
                r.shower ASC,
                r."start" ASC,
                r."end" DESC
        '''))

        column_names = [desc[0] for desc in cur.description]
        write_cur = db_conn.cursor()

        prev_record = None
        delete_stmt = db_conn.convert_stmt('DELETE FROM rate WHERE id = %(id)s')
        for _record in cur:
            self.counter_read += 1
            record = Record(dict(zip(column_names, _record)))
            if not self.drop_tables:
                write_cur.execute(delete_stmt, {'id': record.id})

            if prev_record is None:
                prev_record = record
                continue

            if record in prev_record:
                msg = "Rate observation %s contains observation %s. Observation %s discarded."
                self._log_error(msg % (prev_record.id, record.id, prev_record.id))
                prev_record = record
                continue

            if prev_record == record:
                msg = "Rate observation %s overlaps observation %s. Observation %s discarded."
                self._log_error(msg % (prev_record.id, record.id, record.id))
                continue

            prev_record.write(write_cur, solarlongs, showers)
            self.counter_write += 1
            prev_record = record

        if prev_record is not None:
            prev_record.write(write_cur, solarlongs, showers)
            self.counter_write += 1

        cur.close()
        write_cur.close()
