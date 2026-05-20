import math
from datetime import datetime, timedelta

from astropy import units as u
from astropy.coordinates import GeocentricMeanEcliptic, get_body, solar_system_ephemeris
from astropy.time import Time as AstropyTime


class Sphere:
    """A point in spherical coordinates (longitude, latitude, radius).

    All angles are in radians. Can be constructed from explicit ``(lng, lat)``
    values or by converting a :class:`Cartesian` point.

    :param lng: Longitude in radians (normalised to [0, 2π]).
    :param lat: Latitude in radians.
    :param r: Radius (default 1.0).
    :param c: :class:`Cartesian` point to convert; if given, ``lng``, ``lat``
        and ``r`` are derived from it.
    """

    def __init__(self, lng=0.0, lat=0.0, r=1.0, c=None):
        if c is None:
            self.r = r
            self.lng = lng if lng > 0.0 else lng + 2 * math.pi
            self.lat = lat
            return

        self.r = math.sqrt(math.pow(c.x, 2) + math.pow(c.y, 2) + math.pow(c.z, 2))
        self.lat = math.asin(c.z / self.r)
        if 0.0 == c.x:
            self.lng = (1.0 if c.y > 0.0 else -1) * math.pi / 2
        else:
            self.lng = math.atan2(c.y, c.x)

        if self.lng < 0.0:
            self.lng += 2 * math.pi

    def __str__(self):
        return "lng=%s, lat=%s" % (self.lng, self.lat)


class Location(Sphere):
    """Geographic observer location on the Earth's surface.

    :param lng: Geographic longitude in radians (east positive).
    :param lat: Geographic latitude in radians (north positive).
    """

    def __init__(self, lng=0.0, lat=0.0):
        super().__init__(lng, lat)


class Cartesian:
    """A point in 3-D Cartesian coordinates.

    Can be constructed from explicit ``(x, y, z)`` values or by converting a
    :class:`Sphere` point.

    :param x: X component.
    :param y: Y component.
    :param z: Z component.
    :param s: :class:`Sphere` point to convert; if given, explicit components
        are ignored.
    """

    def __init__(self, x=0.0, y=0.0, z=0.0, s=None):
        if s is None:
            self.x = x
            self.y = y
            self.z = z
            return

        self.x = s.r * math.cos(s.lat) * math.cos(s.lng)
        self.y = s.r * math.cos(s.lat) * math.sin(s.lng)
        self.z = s.r * math.sin(s.lat)

    def __str__(self):
        return "x=%s, y=%s, z=%s" % (self.x, self.y, self.z)


class Ephemeris:
    """Pre-computed heliocentric and geocentric body positions for a single UTC day.

    Fetches Sun and Moon positions via :mod:`astropy` (built-in ephemeris) and
    stores them as :class:`Cartesian` vectors so they can be linearly
    interpolated within the day by :class:`Sky`.

    :param day: Midnight UTC of the day as a :class:`~datetime.datetime`.
    """

    def __init__(self, day):
        self.day = day
        at = AstropyTime(day, format="datetime", scale="utc")
        # Times are UTC; solar-system bodies are returned in GCRS (J2000/ICRS epoch).
        # equinox='J2000' is set explicitly so future Astropy defaults cannot change it.
        with solar_system_ephemeris.set("builtin"):
            sun = get_body("sun", at)
            self.sun_ecliptic = self._cartesian(
                sun.transform_to(GeocentricMeanEcliptic(equinox="J2000"))
            )
            self.sun = self._cartesian(sun)
            self.moon = self._cartesian(get_body("moon", at))

    @staticmethod
    def _cartesian(spherical):
        """Extract Cartesian components from an astropy SkyCoord.

        :param spherical: Astropy sky coordinate object with a ``cartesian``
            attribute exposing ``.x``, ``.y``, ``.z`` in AU.
        :return: :class:`Cartesian` with the extracted components.
        """
        return Cartesian(
            x=spherical.cartesian.x.value,
            y=spherical.cartesian.y.value,
            z=spherical.cartesian.z.value,
        )


class Sky:
    """Astronomical calculations for observation normalisation.

    Caches daily :class:`Ephemeris` objects and interpolates body positions to
    arbitrary UTC times within each day.  All returned angles are in radians
    unless noted otherwise.
    """

    def __init__(self):
        self._days = {}

    def sun(self, t, loc=None):
        """Return the Sun's position at time *t*.

        :param t: UTC time as :class:`~datetime.datetime`.
        :param loc: Observer :class:`Location`. When given, returns horizontal
            coordinates (altitude in ``lat``, azimuth in ``lng``); otherwise
            equatorial (RA, Dec).
        :return: :class:`Sphere` with the Sun's position in radians.
        """
        e0, e1 = self._get_time_range(t)
        coord = self._approx(t, e0.day, e1.day, e0.sun, e1.sun)
        s = Sphere(c=coord)
        if loc is None:
            return Sphere(s.lng, s.lat)

        return self.alt_az(s, t, loc)

    def solarlong(self, t):
        """Return the ecliptic longitude of the Sun (solar longitude) at *t*.

        :param t: UTC time as :class:`~datetime.datetime`.
        :return: Solar longitude in radians, in [0, 2π].
        """
        e0, e1 = self._get_time_range(t)
        sun = Sphere(
            c=self._approx(t, e0.day, e1.day, e0.sun_ecliptic, e1.sun_ecliptic)
        )
        return sun.lng if sun.lng > 0.0 else sun.lng + 2 * math.pi

    def moon(self, t, loc=None):
        """Return the Moon's position at time *t*.

        :param t: UTC time as :class:`~datetime.datetime`.
        :param loc: Observer :class:`Location`. When given, returns horizontal
            coordinates; otherwise equatorial.
        :return: :class:`Sphere` with the Moon's position in radians.
        """
        e0, e1 = self._get_time_range(t)
        coord = self._approx(t, e0.day, e1.day, e0.moon, e1.moon)
        s = Sphere(c=coord)
        if loc is None:
            return Sphere(s.lng, s.lat)

        return self.alt_az(s, t, loc)

    def moon_illumination(self, t):
        """Return the fraction of the Moon's disk that is illuminated at *t*.

        :param t: UTC time as :class:`~datetime.datetime`.
        :return: Illuminated fraction in [0, 1].
        """
        e0, e1 = self._get_time_range(t)
        sun = Sphere(c=self._approx(t, e0.day, e1.day, e0.sun, e1.sun))
        sun.r *= 149597870.7  # AE in km
        moon = Sphere(c=self._approx(t, e0.day, e1.day, e0.moon, e1.moon))
        elongation = math.acos(
            math.sin(sun.lat) * math.sin(moon.lat)
            + math.cos(sun.lat) * math.cos(moon.lat) * math.cos(sun.lng - moon.lng)
        )
        moon_phase_angle = math.atan2(
            sun.r * math.sin(elongation), moon.r - sun.r * math.cos(elongation)
        )
        return (1 + math.cos(moon_phase_angle)) / 2.0

    def _get_time_range(self, t):
        """Return the pair of :class:`Ephemeris` objects bracketing *t* (today and tomorrow).

        :param t: UTC time as :class:`~datetime.datetime`.
        :return: Tuple ``(e0, e1)`` where ``e0`` is the ephemeris for midnight
            of *t*'s date and ``e1`` is for the following midnight.
        """
        t0 = datetime(t.year, t.month, t.day, 0, 0, 0)
        t1 = t0 + timedelta(days=1)
        if t0 not in self._days:
            self._days[t0] = Ephemeris(t0)
        if t1 not in self._days:
            self._days[t1] = Ephemeris(t1)

        return self._days[t0], self._days[t1]

    @staticmethod
    def _approx(t, t0, t1, s0, s1):
        """Linearly interpolate between two :class:`Cartesian` positions.

        :param t: Target time as :class:`~datetime.datetime`.
        :param t0: Start time (midnight of the day) as :class:`~datetime.datetime`.
        :param t1: End time (midnight of the next day) as :class:`~datetime.datetime`.
        :param s0: :class:`Cartesian` position at *t0*.
        :param s1: :class:`Cartesian` position at *t1*.
        :return: Interpolated :class:`Cartesian` position at *t*.
        """
        f = (t - t0) / (t1 - t0)
        return Cartesian(
            x=f * (s1.x - s0.x) + s0.x,
            y=f * (s1.y - s0.y) + s0.y,
            z=f * (s1.z - s0.z) + s0.z,
        )

    @staticmethod
    def sidereal_time(t, loc):
        """Return the mean local sidereal time in radians for observer *loc* at time *t*.

        :param t: UTC time as :class:`~datetime.datetime`.
        :param loc: Observer :class:`Location`.
        :return: Local mean sidereal time in radians.
        """
        at = AstropyTime(t, format="datetime", scale="utc")
        return at.sidereal_time("mean", longitude=loc.lng * u.rad).rad  # type: ignore[attr-defined]

    @classmethod
    def alt_az(cls, s, t, loc):
        """Convert equatorial coordinates to horizontal (altitude/azimuth) coordinates.

        :param s: :class:`Sphere` with equatorial coordinates (RA, Dec in radians).
        :param t: UTC time as :class:`~datetime.datetime`.
        :param loc: Observer :class:`Location`.
        :return: :class:`Sphere` with altitude in ``lat`` and azimuth in ``lng``,
            both in radians.
        """
        st = cls.sidereal_time(t, loc)
        st_diff = st - s.lng
        x = math.sin(loc.lat) * math.cos(s.lat) * math.cos(st_diff) - math.cos(
            loc.lat
        ) * math.sin(s.lat)
        y = math.cos(s.lat) * math.sin(st_diff)
        z = math.cos(loc.lat) * math.cos(s.lat) * math.cos(st_diff) + math.sin(
            loc.lat
        ) * math.sin(s.lat)
        c = Cartesian(x, y, z)
        s = Sphere(c=c)
        return Sphere(s.lng, s.lat)
