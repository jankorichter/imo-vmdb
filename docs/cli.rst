.. _cli:

Command Line Interface
======================

All commands share the same syntax::

    imo-vmdb <command> [options]

The database is configured either via a config file (``-c config.ini``) or via
environment variables.  See :ref:`setup` for configuration details.

initdb
------

Initializes the database schema::

    imo-vmdb initdb -c config.ini

.. warning::
   Running ``initdb`` on an existing database will delete all data in it.

import_csv
----------

Imports one or more CSV files into the database.  The import is the first of
two stages — see `normalize`_ for the second stage.

During import, every record is checked individually.  Records that fail
validation are rejected with an error; records that look suspicious but are
still acceptable trigger a warning.
For the expected column names and format of each file type, see :ref:`csv-import`.

Example — import all 2020 files::

    imo-vmdb import_csv -c config.ini data/*-2020.csv

Available options:

* ``-d`` — delete previously imported data before importing
* ``-p`` — permissive mode (see below)
* ``-r`` — repair mode (see below)

The ``-d`` option is useful when you want to re-import a single file without
running ``cleanup`` first.

**Permissive mode** (``-p``) accepts records that would normally be rejected,
logging a warning instead of an error.  The following cases are affected:

* Observation periods where start time equals end time.
* Sessions with no elevation value (normally a required field).
* Rate observations with a ``teff`` (effective observing time) greater than
  7 hours, up to a maximum of 24 hours.
* Magnitude records where the running magnitude-count sum has a fractional
  remainder at an intermediate step.  The final total across all magnitude
  classes must still be a whole number in all cases.

**Repair mode** (``-r``) attempts to automatically correct certain malformed
values before validation.  A warning is logged for every correction applied.
The following corrections are attempted:

* **Sentinel values in declination** — values ``990`` and ``999`` are treated
  as missing rather than causing a rejection.
* **Sentinel value in right ascension** — a value of ``999`` is treated as
  missing.
* **Asymmetric RA/Dec pair** — if only one of right ascension or declination
  is set, both are cleared to missing.
* **Inverted observation period** — if the end time precedes the start time,
  the two are swapped, provided the resulting duration does not exceed
  0.49 days (~11 h 46 min).
* **Off-by-one-day error** — if the observation period is invalid but becomes
  valid by shifting the end date one day forward or backward, that correction
  is applied (subject to the same maximum duration).

Both options can be combined.

normalize
---------

Normalizes the imported records and enriches observations with computed
astronomical data::

    imo-vmdb normalize -c config.ini

The following data are computed and stored:

* solar longitude,
* position of the radiants,
* position of the sun,
* position of the moon and its illumination,
* position of the field of view,
* radiant altitude with zenith attraction applied.

All positional data are in the horizontal coordinate system.

Further plausibility checks are applied during normalization:

* observations where the sun is above the horizon are rejected,
* overlapping observations within the same session are discarded as duplicates.

.. warning::
   Re-normalizing a session deletes all existing records for that session and
   recreates them from scratch.

After normalization is complete, the raw imported records can be removed with
``cleanup``.

cleanup
-------

Removes raw imported data from the database while preserving all normalized
results::

    imo-vmdb cleanup -c config.ini

web_server
----------

Starts the web server, which always serves the REST API at ``/api/v1``.
The browser-based control panel (Web UI) is opt-in::

    imo-vmdb web_server -c config.ini                  # REST API only
    imo-vmdb web_server -c config.ini --enable-webui   # REST API + Web UI

For a quick start without a config file, pass the database path as an
environment variable::

    IMO_VMDB_DATABASE_DATABASE=./data/vmdb.db imo-vmdb web_server --enable-webui

The server listens on ``http://127.0.0.1:8000`` by default.

Additional options:

* ``--host HOST`` — network interface to bind to (default: ``127.0.0.1``,
  also configurable via ``IMO_VMDB_WEBSERVER_HOST``)
* ``--port PORT`` — port number (default: ``8000``,
  also configurable via ``IMO_VMDB_WEBSERVER_PORT``)
* ``--enable-webui`` — also serve the browser-based control panel at ``/``
  (also configurable via ``IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true``)

To make the server reachable from other machines on the network::

    imo-vmdb web_server -c config.ini --host 0.0.0.0

.. note::
   The web server is intended for local or trusted-network use only.
   It is not hardened for public internet exposure.

   When the server starts, Flask prints the following message:

   .. code-block:: text

      WARNING: This is a development server. Do not use it in a production
      deployment. Use a production WSGI server instead.

   This is expected behaviour.  The warning refers to deployments on a public
   server; it does not apply to local use on your own computer.  You can safely
   ignore it.

See :ref:`webui` for a description of the interface.

.. _csv-export:

export
------

Exports a single table as a semicolon-delimited CSV file or the entire
database as a SQLite file::

    imo-vmdb export <target> [-c config.ini] [-o output_file]

Available CSV targets (one table per call):

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Target
     - Description
   * - ``shower``
     - Meteor shower data from the database
   * - ``radiant``
     - Radiant position data from the database
   * - ``session``
     - Observation sessions
   * - ``rate``
     - Normalised rate observations
   * - ``magnitude``
     - Normalised magnitude observations
   * - ``magnitude_detail``
     - Per-magnitude-class frequency counts

For CSV targets, output goes to stdout when ``-o`` is omitted.

The ``--reimport`` flag is available for ``shower`` and ``radiant``.  It
exports the original embedded reference files in the exact format required for
re-import with ``import_csv``::

    imo-vmdb export shower --reimport -o showers_edited.csv

Without ``--reimport``, all CSV targets — including ``shower`` and
``radiant`` — are exported directly from the database using the field names
documented in :ref:`fields`.

.. _db-export:

Exporting the whole database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The special target ``db`` writes the entire database (normalized
observations and reference data, but not the raw ``imported_*`` tables)
into a single SQLite file::

    imo-vmdb export db -o snapshot.sqlite

The resulting file uses the same schema as a regular imo-vmdb database.
The recipient can use it directly as their own imo-vmdb database.

When ``db`` is the target, ``-o`` is required and ``--reimport`` is not
supported.
