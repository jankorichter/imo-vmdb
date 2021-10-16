import math
from astropy import units as u
from astropy.coordinates import solar_system_ephemeris, get_moon, get_sun
from astropy.coordinates import GeocentricMeanEcliptic
from astropy.time import Time as AstropyTime
from datetime import datetime, timedelta


class Sphere(object):
    def __init__(self, lng=None, lat=None, r=1.0, c=None):
        if c is None:
            self.r = r
            self.lng = lng if lng > 0.0 else lng + 2 * math.pi
            self.lat = lat
            return

        self.r = math.sqrt(math.pow(c.x, 2) + math.pow(c.y, 2) + math.pow(c.z, 2))
        self.lat = math.asin(c.z/self.r)
        if 0.0 == c.x:
            self.lng = (1.0 if c.y > 0.0 else -1) * math.pi/2
        else:
            self.lng = math.atan2(c.y, c.x)

        if self.lng < 0.0:
            self.lng += 2 * math.pi

    def __str__(self):
        return 'lng=%s, lat=%s' % (self.lng, self.lat)


class Location(Sphere):
    def __init__(self, lng=None, lat=None):
        super().__init__(lng, lat)


class Cartesian(object):
    def __init__(self, x=None, y=None, z=None, s=None):
        if s is None:
            self.x = x
            self.y = y
            self.z = z
            return

        self.x = s.r * math.cos(s.lat) * math.cos(s.lng)
        self.y = s.r * math.cos(s.lat) * math.sin(s.lng)
        self.z = s.r * math.sin(s.lat)

    def __str__(self):
        return 'x=%s, y=%s, z=%s' % (self.x, self.y, self.z)


class Ephemeris(object):

    def __init__(self, day):
        self.day = day
        at = AstropyTime(day, format='datetime', scale='utc')
        with solar_system_ephemeris.set('builtin'):
            sun = get_sun(at)
            self.sun_ecliptic = self._cartesian(sun.transform_to(GeocentricMeanEcliptic))
            self.sun = self._cartesian(sun)
            self.moon = self._cartesian(get_moon(at))

    @staticmethod
    def _cartesian(spherical):
        return Cartesian(
            x=spherical.cartesian.x.value,
            y=spherical.cartesian.y.value,
            z=spherical.cartesian.z.value,
        )


class Sky(object):

    def __init__(self):
        self._days = {}

    def sun(self, t, loc=None):
        e0, e1 = self._get_time_range(t)
        coord = self._approx(t, e0.day, e1.day, e0.sun, e1.sun)
        s = Sphere(c=coord)
        if loc is None:
            return Sphere(s.lng, s.lat)

        return self.alt_az(s, t, loc)

    def solarlong(self, t):
        e0, e1 = self._get_time_range(t)
        sun = Sphere(c=self._approx(t, e0.day, e1.day, e0.sun_ecliptic, e1.sun_ecliptic))
        return sun.lng if sun.lng > 0.0 else sun.lng + 2*math.pi

    def moon(self, t, loc=None):
        e0, e1 = self._get_time_range(t)
        coord = self._approx(t, e0.day, e1.day, e0.moon, e1.moon)
        s = Sphere(c=coord)
        if loc is None:
            return Sphere(s.lng, s.lat)

        return self.alt_az(s, t, loc)

    def moon_illumination(self, t):
        e0, e1 = self._get_time_range(t)
        sun = Sphere(c=self._approx(t, e0.day, e1.day, e0.sun, e1.sun))
        sun.r *= 149597870.7  # AE in km
        moon = Sphere(c=self._approx(t, e0.day, e1.day, e0.moon, e1.moon))
        elongation = math.acos(
            math.sin(sun.lat) * math.sin(moon.lat) +
            math.cos(sun.lat) * math.cos(moon.lat) * math.cos(sun.lng - moon.lng)
        )
        moon_phase_angle = math.atan2(
            sun.r * math.sin(elongation),
            moon.r - sun.r * math.cos(elongation)
        )
        return (1 + math.cos(moon_phase_angle)) / 2.0

    def _get_time_range(self, t):
        t0 = datetime(t.year, t.month, t.day, 0, 0, 0)
        t1 = t0 + timedelta(days=1)
        if t0 not in self._days:
            self._days[t0] = Ephemeris(t0)
        if t1 not in self._days:
            self._days[t1] = Ephemeris(t1)

        return self._days[t0], self._days[t1]

    @staticmethod
    def _approx(t, t0, t1, s0, s1):
        f = ((t - t0) / (t1 - t0))
        return Cartesian(
            x=f * (s1.x - s0.x) + s0.x,
            y=f * (s1.y - s0.y) + s0.y,
            z=f * (s1.z - s0.z) + s0.z,
        )

    @staticmethod
    def sidereal_time(t, loc):
        at = AstropyTime(t, format='datetime', scale='utc')
        return at.sidereal_time('mean', longitude=loc.lng * u.rad).rad

    @classmethod
    def alt_az(cls, s, t, loc):
        st = cls.sidereal_time(t, loc)
        st_diff = st - s.lng
        x = math.sin(loc.lat) * math.cos(s.lat) * math.cos(st_diff) - math.cos(loc.lat) * math.sin(s.lat)
        y = math.cos(s.lat) * math.sin(st_diff)
        z = math.cos(loc.lat) * math.cos(s.lat) * math.cos(st_diff) + math.sin(loc.lat) * math.sin(s.lat)
        c = Cartesian(x, y, z)
        s = Sphere(c=c)
        return Sphere(s.lng, s.lat)
