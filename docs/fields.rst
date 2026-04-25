.. _fields:

Field Reference
===============

This reference covers all fields as they appear in the database, the REST API,
and CSV exports.  Field names are identical across all three interfaces.

Entity Relationships
--------------------

.. code-block:: text

    obs_session (id)
      │
      ├──< rate (session_id) ──────────────── rate_magnitude (rate_id, magn_id) >──┐
      │                                                                            │
      └──< magnitude (session_id) ─────────────────────────────────────────────────┘
               │
               └──< magnitude_detail (id → magnitude.id)

    shower   ···  rate.shower, magnitude.shower  (IAU code)
    radiant  ···  used during normalization only  (uses IAU code)

``obs_session`` is the root.  Each session can have many ``rate`` and
``magnitude`` records.  ``rate_magnitude`` links a rate observation to the
magnitude observation covering the same period (many-to-one on the magnitude
side).  ``magnitude_detail`` holds the per-class breakdown for each magnitude
observation.  ``shower`` and ``radiant`` are lookup tables referenced by IAU
code, not by foreign key.

Sessions (``obs_session``)
--------------------------

* ``id`` — unique identifier of the session
* ``longitude`` — observer longitude in degrees
* ``latitude`` — observer latitude in degrees
* ``elevation`` — height above mean sea level in km
* ``country`` — country name
* ``city`` — name of the observation site
* ``observer_id`` — observer id (*optional*)
* ``observer_name`` — observer name (*optional*)

Rates (``rate``)
----------------

All rate observations are associated with an ``obs_session`` record.
``shower`` is absent when the observation covers sporadic meteors or no shower
has been assigned.

* ``id`` — unique identifier of the rate observation
* ``shower`` — IAU code of the shower (*optional*)
* ``period_start`` — start of the observation period
* ``period_end`` — end of the observation period
* ``sl_start`` — solar longitude at period start in degrees
* ``sl_end`` — solar longitude at period end in degrees
* ``session_id`` — reference to the session
* ``freq`` — count of observed meteors
* ``lim_mag`` — limiting magnitude
* ``t_eff`` — net observed time in hours
* ``f`` — cloud cover correction factor
* ``sidereal_time`` — sidereal time in degrees
* ``sun_alt`` — solar altitude in degrees
* ``sun_az`` — solar azimuth in degrees
* ``moon_alt`` — lunar altitude in degrees
* ``moon_az`` — lunar azimuth in degrees
* ``moon_illum`` — lunar illumination (0.0–1.0)
* ``field_alt`` — altitude of the field of view in degrees (*optional*)
* ``field_az`` — azimuth of the field of view in degrees (*optional*)
* ``rad_alt`` — radiant altitude in degrees, zenith attraction applied (*optional*)
* ``rad_az`` — radiant azimuth in degrees (*optional*)

Magnitudes (``magnitude``)
--------------------------

All magnitude observations are associated with an ``obs_session`` record.
``shower`` is absent for sporadic meteors.  There are no records in this table
where no meteors were observed (``freq`` is always ≥ 1).

* ``id`` — unique identifier of the magnitude observation
* ``shower`` — IAU code of the shower (*optional*)
* ``period_start`` — start of the observation period
* ``period_end`` — end of the observation period
* ``sl_start`` — solar longitude at period start
* ``sl_end`` — solar longitude at period end
* ``session_id`` — reference to the session
* ``freq`` — total count of observed meteors
* ``mean`` — mean magnitude
* ``lim_mag`` — limiting magnitude (*optional*)

Magnitude Details (``magnitude_detail``)
-----------------------------------------

Contains the per-class frequency breakdown for each magnitude observation.
Only classes where at least one meteor was observed are stored — ``freq`` is
always > 0 and may be fractional.

* ``id`` — reference to the magnitude observation
* ``magn`` — magnitude class
* ``freq`` — count of observed meteors in this class

Rates and Magnitudes (``rate_magnitude``)
-----------------------------------------

Associates rate observations with magnitude observations.  A magnitude
observation may correspond to multiple rate observations, but not vice versa.

* ``rate_id`` — reference to the rate observation
* ``magn_id`` — reference to the magnitude observation
* ``equals`` — ``true`` if the rate observation covers exactly the same period
  as the magnitude observation

Showers (``shower``)
--------------------

Lookup table for meteor showers.  Used during import to resolve shower codes
and to supply default radiant positions when no drift data is available.

* ``id`` — unique identifier
* ``iau_code`` — IAU shower code
* ``name`` — shower name
* ``start_month`` — month of activity start
* ``start_day`` — day of activity start
* ``end_month`` — month of activity end
* ``end_day`` — day of activity end
* ``peak_month`` — month of peak activity (*optional*)
* ``peak_day`` — day of peak activity (*optional*)
* ``ra`` — mean right ascension of the radiant in degrees (*optional*)
* ``dec`` — mean declination of the radiant in degrees (*optional*)
* ``v`` — entry velocity in km/s (*optional*)
* ``r`` — population index (*optional*)
* ``zhr`` — zenithal hourly rate at peak (*optional*)

Radiants (``radiant``)
----------------------

Lookup table for radiant drift positions.  Used during normalization to
interpolate the radiant position for a given date.

* ``shower`` — IAU shower code
* ``month`` — month
* ``day`` — day
* ``ra`` — right ascension of the radiant in degrees
* ``dec`` — declination of the radiant in degrees
