.. _cli:

Command Line Interface
======================

All commands share the same syntax::

    python -m imo_vmdb <command> [options]

The database is configured either via a config file (``-c config.ini``) or via
environment variables.  See :ref:`setup` for configuration details.

initdb
------

Initializes the database schema.  **All existing data will be deleted.**::

    python -m imo_vmdb initdb -c config.ini

import_csv
----------

Imports one or more CSV files into the database.  The import is the first of
two stages — see `normalize`_ for the second stage.

During import, every record is checked individually.  Records that fail
validation are rejected with an error; records that look suspicious but are
still acceptable trigger a warning.
For the expected column names and format of each file type, see :ref:`csv-import`.

Example — import all 2020 files::

    python -m imo_vmdb import_csv -c config.ini data/*-2020.csv

Available options:

* ``-d`` — delete previously imported data before importing
* ``-p`` — permissive mode: accept records that would normally be rejected with
  a warning instead of an error
* ``-r`` — attempt to repair records: detect and correct swapped start/end
  times, strip invalid optional fields

The ``-d`` option is useful when you want to re-import a single file without
running ``cleanup`` first.

normalize
---------

Normalizes the imported records and enriches observations with computed
astronomical data::

    python -m imo_vmdb normalize -c config.ini

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

    python -m imo_vmdb cleanup -c config.ini

web_server
----------

Starts the web server, which provides both the browser-based control panel
and the REST API::

    python -m imo_vmdb web_server -c config.ini

The server listens on ``http://127.0.0.1:8000`` by default.

Additional options:

* ``--host HOST`` — network interface to bind to (default: ``127.0.0.1``)
* ``--port PORT`` — port number (default: ``8000``)

To make the server reachable from other machines on the network::

    python -m imo_vmdb web_server -c config.ini --host 0.0.0.0

.. note::
   The web server is intended for local or trusted-network use only.
   It is not hardened for public internet exposure.

See :ref:`webui` for a description of the interface.

.. _csv-export:

export
------

Exports a table as a semicolon-delimited CSV file::

    python -m imo_vmdb export <table> [-c config.ini] [-o output.csv]

Available tables:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Table
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
   * - ``rate_magnitude``
     - Rate-to-magnitude cross-reference

Without ``-o``, output goes to stdout.

The ``--reimport`` flag is available for ``shower`` and ``radiant``.  It
exports the original embedded reference files in the exact format required for
re-import with ``import_csv``::

    python -m imo_vmdb export shower --reimport -o showers_edited.csv

Without ``--reimport``, all tables — including ``shower`` and ``radiant`` —
are exported directly from the database using the field names documented in
:ref:`fields`.

