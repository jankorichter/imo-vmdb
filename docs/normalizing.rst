.. _normalization:

Normalization
=============

Normalization establishes relationships between the :ref:`imported <import>` records.
The imported observations are thereby enriched with additional informations:

* solarlong,
* position of the radiants,
* position of the sun,
* position of the moon and its illumination,
* position of the field of view,
* determination of the correction factor of the radiant altitude for the rate calculation,

where all position data are coordinates in the horizontal coordinate system.
Normalization is started with the command ``normalize``::

    python -m imo_vmdb normalize -c config.ini


Further plausibility checks take place during normalization.
The position information is used, for example, to check whether the sun is below the horizon.
If this is not the case, the observation will not be accepted with an error message.
It also checks whether observations within an observation session overlap in time.
Such duplicate observations are also discarded.

For normalization, the principle applies that already existing data records are overwritten.

.. WARNING::
   For example, if an observation session is read in, then all existing records of this session will be deleted.
   Thus the complete session is recreated in the database.

After normalization is complete, the imported records can be removed from the database with ``cleanup``.
