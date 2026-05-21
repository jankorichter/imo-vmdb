.. _csv-import:

CSV files
=========

General
*******

The imo-vmdb software imports data from CSV files where columns are separated by semicolons.
Columns are recognized regardless of their order. imo-vmdb does not differentiate between
uppercase and lowercase in column names.

The type of the imported CSV file is identified based on the column names.
It is important that all required columns are included in the CSV file.
However, the software is capable of ignoring additional columns that are not
necessary for its application. This functionality allows the software to process
data files containing extra, non-relevant information without the need for modifying
the CSV file.

For many columns, alternative names are accepted. The name listed first in each
entry below matches the column name used by the CSV export and the REST API; the
further names are kept for compatibility with the original IMO CSV files. A CSV
file must use only one name per column — supplying the same column under two of
its alternative names is rejected with an error.

Sessions
********

CVS files with information about the meteor observation ,
must contain the following columns:

* ``id``, ``session_id``, ``session id``: identifier of the session
* ``longitude``: location's longitude in degrees
* ``latitude``: location's latitude in degrees
* ``elevation``: height above mean sea level in km
* ``country``: country name
* ``location_name``, ``city``: location name
* ``observer_id``, ``observer id``: observer id (*optional*)
* ``observer_name``, ``actual observer name``: observer name (*optional*)

Rates
*****

Rate observations are assigned to an observation session.
The following columns must exist in the CVS file to be imported:

* ``id``, ``rate_id``, ``rate id``: unique identifier of the rate observation
* ``shower``: IAU code of the shower or `SPO`
* ``period_start``, ``start date``: start of observation
* ``period_end``, ``end date``: end of observation
* ``session_id``, ``obs session id``: reference to the session
* ``freq``, ``number``: count of observed meteors
* ``lim_magn``, ``lm``: limiting magnitude
* ``t_eff``, ``teff``: net observed time in hours
* ``f``: correction factor of cloud cover
* ``ra``: right ascension of the field of view in degrees (*optional*)
* ``dec``, ``decl``: declination of the field of view in degrees (*optional*)
* ``user_id``, ``user id``: user id (*optional*)
* ``method``: method (*optional*)

Magnitudes
**********

Magnitude observations are assigned to an observation session.
The following columns must exist in the CVS file to be imported:

* ``id``, ``magnitude_id``, ``magnitude id``: unique identifier of the magnitude observation
* ``shower``: IAU code of the shower or `SPO`
* ``period_start``, ``start date``: start of observation
* ``period_end``, ``end date``: end of observation
* ``session_id``, ``obs session id``: reference to session
* ``mag_n6``, ``mag n6``: count of observed meteors with magnitude ``-6``
* ``mag_n5``, ``mag n5``: count of observed meteors with magnitude ``-5``
* ``mag_n4``, ``mag n4``: count of observed meteors with magnitude ``-4``
* ``mag_n3``, ``mag n3``: count of observed meteors with magnitude ``-3``
* ``mag_n2``, ``mag n2``: count of observed meteors with magnitude ``-2``
* ``mag_n1``, ``mag n1``: count of observed meteors with magnitude ``-1``
* ``mag_0``, ``mag 0``: count of observed meteors with magnitude ``0``
* ``mag_1``, ``mag 1``: count of observed meteors with magnitude ``1``
* ``mag_2``, ``mag 2``: count of observed meteors with magnitude ``2``
* ``mag_3``, ``mag 3``: count of observed meteors with magnitude ``3``
* ``mag_4``, ``mag 4``: count of observed meteors with magnitude ``4``
* ``mag_5``, ``mag 5``: count of observed meteors with magnitude ``5``
* ``mag_6``, ``mag 6``: count of observed meteors with magnitude ``6``
* ``mag_7``, ``mag 7``: count of observed meteors with magnitude ``7``
* ``user_id``, ``user id``: user id (*optional*)

Showers
*******

The CSV file for meteor showers contains information about their activity period.
The radiant position is used if no radiant drift has been specified.
The following columns must exist in the CVS file to be imported:

* ``id``: unique identifier of the shower
* ``iau_code``: IAU code of the shower
* ``name``: name of the shower
* ``start``: month and day of the beginning of the shower activity
* ``end``: month and day of the end of the shower activity
* ``peak``: month and day of the peak of the shower activity (*optional*)
* ``ra``: mean right ascension of the radiant position in degrees (*optional*)
* ``dec``, ``de``: mean declination of the radiant position in degrees (*optional*)
* ``v``: velocity in km per second (*optional*)
* ``r``: population index (*optional*)
* ``zhr``: mean ZHR in meteors per hour (*optional*)

Radiants
********

This CVS file contains the radiant positions of the meteor showers.
The following columns must exist in the CVS file to be imported:

* ``shower``: IAU code of the shower
* ``month``: month
* ``day``: day
* ``ra``: right ascension of the radiant position in degrees
* ``dec``: declination of the radiant position in degrees
