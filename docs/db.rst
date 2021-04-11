
The Database
============

Sessions
********

The ``obs_session`` table contains all observation sessions.

* ``id`` identifier of the session
* ``longitude`` location's longitude in degrees
* ``latitude`` location's latitude in degrees
* ``elevation`` height above mean sea level in km
* ``observer_name`` observer name
* ``country`` country name
* ``city`` location name


Rates
*****

The ``rate`` table contains all rate observations.
All of these observations are associated with the ``obs_session`` table.
A meteor shower (``shower``) is not provided if it is an observation of sporadic meteors or no meteor shower has been associated.

* ``id`` unique identifier of the rate observation
* ``shower`` IAU code of the shower (*optional*)
* ``period_start`` start of observation
* ``period_end`` start of observation
* ``sl_start`` solarlong at start of observation in degrees
* ``sl_end`` solarlong at start of observation in degrees
* ``session_id`` reference to the session
* ``freq`` count of observed meteors
* ``lim_mag`` limiting magnitude
* ``t_eff`` net observed time in hours
* ``f`` correction factor of cloud cover
* ``sun_alt`` altitude of the sun in degrees
* ``sun_az`` azimuth of the sun in degrees
* ``moon_alt`` altitude of the moon in degrees
* ``moon_az`` azimuth of the moon in degrees
* ``moon_illum`` illumination of the moon (0.0 .. 1.0)
* ``field_alt`` altitude of the field of view in degrees (*optional*)
* ``field_az`` azimuth of the field of view in degrees (*optional*)
* ``rad_alt`` altitude of the radiant in degrees (*optional*)
* ``rad_az`` azimuth of the radiant in degrees (*optional*)
* ``rad_corr`` Correction of the altitude of the radiant (*optional*)


Magnitudes
**********

The ``magnitude`` table contains all rate observations.
All of these observations are associated with the ``obs_session`` table.
A meteor shower (``shower``) is not provided if it is an observation of sporadic meteors or no meteor shower has been associated.
There are no observations in this table where no meteors were observed.

* ``id`` unique identifier of the magnitude observation,
* ``shower`` IAU code of the shower (*optional*)
* ``period_start`` start of observation
* ``period_end`` start of observation
* ``sl_start`` solarlong at start of observation
* ``sl_end`` solarlong at start of observation
* ``session_id`` reference to session
* ``freq`` total count of observed meteors
* ``mean`` mean magnitude of observed meteors
* ``lim_mag`` real NULL,

The table ``magnitude_detail`` contains the observed count of meteors.
There are only entries in this table where meteors were observed.
Therefore, the meteor count ``freq`` is always greater than 0.
Note that the count of observed meteors does not have to be an integer.
So it could also be that half meteors were observed.

* ``id`` identifier of the magnitude observation,
* ``magn`` magnitude
* ``freq`` count of observed meteors


Rates and Magnitudes
********************

The ``rate_magnitude`` table associates rate observations with magnitude observations.
One magnitude observation can have multiple rate observations associated with it, but never vice versa.
If a magnitude observation corresponds exactly to a rate observation, then ``equals`` is true.

* ``rate_id`` unique identifier of the rate observation
* ``magn_id`` identifier of the magnitude observation
* ``equals`` true if the rate observation is equal to the magnitude observation


Showers
*******

The ``shower`` table is a lookup table for showers.
It is not referenced anywhere and is used especially during data import.

* ``id`` unique identifier of the shower
* ``iau_code`` IAU code of the shower
* ``name`` name of the shower
* ``start_month`` month of the beginning of the shower activity
* ``start_day`` day of the beginning of the shower activity
* ``end_month`` month of the end of the shower activity
* ``end_day`` day of the end of the shower activity
* ``peak_month`` month of the peak of the shower activity (*optional*)
* ``peak_day`` day of the peak of the shower activity (*optional*)
* ``ra`` mean right ascension of the radiant position in degrees (*optional*)
* ``dec`` mean declination of the radiant position in degrees (*optional*)
* ``v`` velocity in km per second (*optional*)
* ``r`` population index (*optional*)
* ``zhr`` mean ZHR in meteors per hour (*optional*)


Radiants
********

The ``radiant`` table is a lookup table for radiant positions.
It is not referenced anywhere and is used especially during data import.

* ``shower`` IAU code of the shower
* ``month`` month
* ``day`` day
* ``ra`` right ascension of the radiant position in degrees
* ``dec`` declination of the radiant position in degrees
