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

Sessions
********

CVS files with information about the meteor observation ,
must contain the following columns:

* ``session id`` identifier of the session
* ``longitude`` location's longitude in degrees
* ``latitude`` location's latitude in degrees
* ``elevation`` height above mean sea level in km
* ``country`` country name
* ``city`` location name
* ``observer id`` observer id (*optional*)
* ``actual observer name`` observer name (*optional*)

Rates
*****

Rate observations are assigned to an observation session.
The following columns must exist in the CVS file to be imported:

* ``rate id`` unique identifier of the rate observation
* ``shower`` IAU code of the shower or `SPO`
* ``start date`` start of observation
* ``end date`` end of observation
* ``obs session id`` reference to the session
* ``number`` count of observed meteors
* ``lm`` limiting magnitude
* ``teff`` net observed time in hours
* ``f`` correction factor of cloud cover
* ``ra`` right ascension of the field of view in degrees (*optional*)
* ``dec`` declination of the field of view in degrees (*optional*)
* ``user id`` user id (*optional*)
* ``method`` method (*optional*)

Magnitudes
**********

Magnitude observations are assigned to an observation session.
The following columns must exist in the CVS file to be imported:

* ``magnitude id`` unique identifier of the magnitude observation,
* ``shower`` IAU code of the shower or `SPO`
* ``start date`` start of observation
* ``end date`` end of observation
* ``obs session id`` reference to session
* ``mag n6`` count of observed meteors with magnitude ``-6``
* ``mag n5`` count of observed meteors with magnitude ``-5``
* ``mag n4`` count of observed meteors with magnitude ``-4``
* ``mag n3`` count of observed meteors with magnitude ``-3``
* ``mag n2`` count of observed meteors with magnitude ``-2``
* ``mag n1`` count of observed meteors with magnitude ``-1``
* ``mag 0`` count of observed meteors with magnitude ``0``
* ``mag 1`` count of observed meteors with magnitude ``1``
* ``mag 2`` count of observed meteors with magnitude ``2``
* ``mag 3`` count of observed meteors with magnitude ``3``
* ``mag 4`` count of observed meteors with magnitude ``4``
* ``mag 5`` count of observed meteors with magnitude ``5``
* ``mag 6`` count of observed meteors with magnitude ``6``
* ``mag 7`` count of observed meteors with magnitude ``7``
* ``user id`` user id (*optional*)

Showers
*******

The CSV file for meteor showers contains information about their activity period.
The radiant position is used if no radiant drift has been specified.
The following columns must exist in the CVS file to be imported:

* ``id`` unique identifier of the shower
* ``iau_code`` IAU code of the shower
* ``name`` name of the shower
* ``start`` month and day of the beginning of the shower activity
* ``end`` month and day of the end of the shower activity
* ``peak`` month and day of the peak of the shower activity (*optional*)
* ``ra`` mean right ascension of the radiant position in degrees (*optional*)
* ``de`` mean declination of the radiant position in degrees (*optional*)
* ``v`` velocity in km per second (*optional*)
* ``r`` population index (*optional*)
* ``zhr`` mean ZHR in meteors per hour (*optional*)

Radiants
********

This CVS file contains the radiant positions of the meteor showers.
The following columns must exist in the CVS file to be imported:

* ``shower`` IAU code of the shower
* ``month`` month
* ``day`` day
* ``ra`` right ascension of the radiant position in degrees
* ``dec`` declination of the radiant position in degrees
