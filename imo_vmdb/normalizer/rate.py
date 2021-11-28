import math
from imo_vmdb.db import DBException
from imo_vmdb.model.sky import Location, Sphere
from imo_vmdb.normalizer import BaseRecord, BaseNormalizer, NormalizerException


class Record(BaseRecord):
    _insert_stmt = '''
        INSERT INTO rate (
            id,
            shower,
            period_start,
            period_end,
            sl_start,
            sl_end,
            session_id,
            freq,
            lim_mag,
            t_eff,
            f,
            sidereal_time,
            sun_alt,
            sun_az,
            moon_alt,
            moon_az,
            moon_illum,
            field_alt,
            field_az,
            rad_alt,
            rad_az
        ) VALUES (
            %(id)s,
            %(shower)s,
            %(period_start)s,
            %(period_end)s,
            %(sl_start)s,
            %(sl_end)s,
            %(session_id)s,
            %(freq)s,
            %(lim_mag)s,
            %(t_eff)s,
            %(f)s,
            %(sidereal_time)s,
            %(sun_alt)s,
            %(sun_az)s,
            %(moon_alt)s,
            %(moon_az)s,
            %(moon_illum)s,
            %(field_alt)s,
            %(field_az)s,
            %(rad_alt)s,
            %(rad_az)s
        )
    '''

    def __init__(self, record):
        super().__init__(record)
        self.freq = record['freq']
        self.lm = record['lm']
        self.t_eff = record['t_eff']
        self.f = record['f']
        self.ra = record['ra']
        self.dec = record['dec']
        self.loc = Location(
            math.radians(record['longitude']),
            math.radians(record['latitude'])
        )

    @classmethod
    def init_stmt(cls, db_conn):
        cls._insert_stmt = db_conn.convert_stmt(cls._insert_stmt)

    @staticmethod
    def _zenith_coor(alt, v):
        # Peter S. Gural, WGN 29:4 (2000), p134-138
        z = math.pi/2.0 - alt
        w = math.sqrt(pow(v, 2) + 123.06)
        zo = z / 2.0 + math.asin(v * math.sin(z / 2.0) / w)
        return math.pi/2.0 - zo

    def write(self, cur, sky, showers):
        iau_code = self.shower
        t_abs = self.end - self.start
        t_mean = self.start + t_abs / 2
        sl_start = sky.solarlong(self.start)
        sl_end = sky.solarlong(self.end)
        shower = showers[iau_code] if iau_code in showers else None
        radiant = shower.get_radiant(t_mean) if shower is not None else None

        field_alt = None
        field_az = None
        if self.ra is not None and self.dec is not None:
            field = sky.alt_az(
                Sphere(math.radians(self.ra), math.radians(self.dec)),
                t_mean,
                self.loc
            )
            field_alt = math.degrees(field.lat)
            field_az = math.degrees(field.lng)

        if field_alt is not None and field_alt < 0.0:
            msg = "session %s: field is below horizon (%s degrees)." % (self.session_id, round(field_alt))
            raise NormalizerException(msg)

        sun = sky.sun(t_mean, self.loc)
        if sun.lat > 0.0:
            msg = "session %s: sun is above horizon (%s degrees)."
            msg = msg % (self.session_id, round(math.degrees(sun.lat)))
            raise NormalizerException(msg)

        moon = sky.moon(t_mean, self.loc)
        moon_illumination = sky.moon_illumination(t_mean)

        rad_alt = None
        rad_az = None
        if radiant is not None:
            rad_radec = Sphere(math.radians(radiant.ra), math.radians(radiant.dec))
            rad_coord = sky.alt_az(rad_radec, t_mean, self.loc)
            rad_az = math.degrees(rad_coord.lng)
            rad_alt = math.degrees(self._zenith_coor(rad_coord.lat, shower.v))

        if rad_alt is not None and rad_alt < -5.0:
            msg = "session %s: radiant of %s is too far below the horizon (%s degrees)."
            msg = msg % (self.session_id, iau_code, round(rad_alt))
            raise NormalizerException(msg)

        rate = {
            'id': self.id,
            'shower': iau_code,
            'period_start': self.start,
            'period_end': self.end,
            'sl_start': math.degrees(sl_start),
            'sl_end': math.degrees(sl_end),
            'session_id': self.session_id,
            'freq': self.freq,
            'lim_mag': self.lm,
            't_eff': self.t_eff,
            'f': self.f,
            'sidereal_time': math.degrees(sky.sidereal_time(t_mean, self.loc)),
            'sun_alt': math.degrees(sun.lat),
            'sun_az': math.degrees(sun.lng),
            'moon_alt': math.degrees(moon.lat),
            'moon_az': math.degrees(moon.lng),
            'moon_illum': moon_illumination,
            'field_alt': field_alt,
            'field_az': field_az,
            'rad_alt': rad_alt,
            'rad_az': rad_az
        }

        try:
            cur.execute(self._insert_stmt, rate)
        except Exception as e:
            raise DBException(str(e))


class RateNormalizer(BaseNormalizer):

    def __init__(self, db_conn, logger, sky, showers):
        super().__init__(db_conn, logger)
        self._sky = sky
        self._showers = showers
        Record.init_stmt(db_conn)

    def run(self):
        db_conn = self._db_conn
        try:
            cur = db_conn.cursor()
            cur.execute(db_conn.convert_stmt('''
                SELECT
                    r.id,
                    s.longitude,
                    s.latitude,
                    s.elevation,
                    s.observer_id AS "session_observer_id",
                    r.shower,
                    r.session_id,
                    r.observer_id,
                    r."start",
                    r."end",
                    r.t_eff,
                    r.f,
                    r.lm,
                    r.ra,
                    r.dec,
                    r."number" AS freq
                FROM imported_rate as r
                INNER JOIN obs_session as s ON s.id = r.session_id
                ORDER BY
                    r.session_id ASC,
                    r.shower ASC,
                    r."start" ASC,
                    r."end" DESC
            '''))
        except Exception as e:
            raise DBException(str(e))

        column_names = [desc[0] for desc in cur.description]

        try:
            write_cur = db_conn.cursor()
        except Exception as e:
            raise DBException(str(e))

        prev_record = None
        delete_stmt = db_conn.convert_stmt('DELETE FROM rate WHERE id = %(id)s')
        for _record in cur:
            self.counter_read += 1
            record = Record(dict(zip(column_names, _record)))

            if record.observer_id != record.session_observer_id:
                msg = "session %s: observer ID of the rate observation is different"
                msg += " from the observer ID of the session. Observation %s discarded."
                self._log_error(msg % (record.session_id, record.id))
                prev_record = record
                continue

            try:
                write_cur.execute(delete_stmt, {'id': record.id})
            except Exception as err:
                raise DBException(str(err))

            if prev_record is None:
                prev_record = record
                continue

            if record in prev_record:
                msg = "session %s: rate observation %s contains observation %s. Observation %s discarded."
                self._log_error(msg % (record.session_id, prev_record.id, record.id, prev_record.id))
                prev_record = record
                continue

            if prev_record == record:
                msg = "session %s: rate observation %s overlaps observation %s. Observation %s discarded."
                self._log_error(msg % (record.session_id, prev_record.id, record.id, record.id))
                continue

            try:
                prev_record.write(write_cur, self._sky, self._showers)
            except NormalizerException as err:
                prev_record = record
                self._log_error(str(err))
                continue

            self.counter_write += 1
            prev_record = record

        if prev_record is not None:
            try:
                prev_record.write(write_cur, self._sky, self._showers)
            except NormalizerException as err:
                self._log_error(str(err))
            self.counter_write += 1

        try:
            cur.close()
            write_cur.close()
        except Exception as e:
            raise DBException(str(e))
