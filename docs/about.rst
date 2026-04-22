About imo-vmdb
==============

*imo-vmdb* processes visual meteor observation data from the
`Visual Meteor Database (VMDB) <https://www.imo.net/members/imo_vmdb/>`_
of the `International Meteor Organization (IMO) <https://www.imo.net/>`_.

What it does
------------

The IMO distributes observation data as CSV files.  These raw files contain
counts and times, but lack the derived quantities needed for most analyses —
such as solar longitude, radiant altitude, sun and moon positions.

*imo-vmdb* imports the raw CSV data, validates it, and then *normalizes* it:
each observation is enriched with computed astronomical properties using
`astropy <https://www.astropy.org/>`_:

* **Solar longitude** at the start and end of the observation
* **Radiant position** (altitude and azimuth) in horizontal coordinates,
  with zenith attraction applied
* **Sun position** (altitude and azimuth)
* **Moon position** (altitude, azimuth) and illumination
* **Field-of-view position** (altitude and azimuth)
* **Radiant correction factor** for the ZHR calculation

This enrichment is the core value of *imo-vmdb*: filtering and grouping
observations by these derived quantities — e.g. "all Perseid observations
with the radiant above 30°" — becomes straightforward.

Accessing the data
------------------

Normalised data can be accessed in three ways:

* **REST API** — query observations as JSON, filtered by shower, date range,
  solar longitude, and more; see :ref:`rest-api`.
* **CSV export** — download tables directly from the web UI or CLI;
  see :ref:`csv-export`.
* **Direct database access** — SQLite, PostgreSQL, or MySQL;
  field reference at :ref:`fields`.

Getting started
---------------

The fastest way to get started is the Docker image — no local Python
installation required:

* **Docker / Web UI**: see :ref:`setup`.
* **Python / CLI**: see :ref:`setup`.
