.. _api:

Python API
==========

The ``imo_vmdb`` package provides a Python API that can be used independently
of any web framework or HTTP connection.  It covers importing, normalising,
cleaning up, exporting, and querying meteor observation data.

Database connection
-------------------

.. autoclass:: imo_vmdb.DBAdapter
   :members:

The keys of the *config* dict correspond directly to the ``[database]``
section of the configuration file (see :ref:`setup`).  Examples:

.. code-block:: python

   import imo_vmdb

   # SQLite
   db = imo_vmdb.DBAdapter({"database": "/path/to/vmdb.db"})

   # PostgreSQL
   db = imo_vmdb.DBAdapter({
       "module": "psycopg2",
       "database": "vmdb",
       "user": "vmdb",
       "host": "localhost",
   })

   # MySQL
   db = imo_vmdb.DBAdapter({
       "module": "pymysql",
       "database": "vmdb",
       "user": "vmdb",
   })

.. autoclass:: imo_vmdb.DBException
   :members:

Operations
----------

.. automodule:: imo_vmdb
   :members: cleanup, initdb, normalize, export_table, export_db

Exporting a whole database
~~~~~~~~~~~~~~~~~~~~~~~~~~

:func:`~imo_vmdb.export_db` writes the normalized observations and
reference data of a source database into an empty SQLite destination,
using the same schema as a regular imo-vmdb database.  The resulting
file can be shared and re-used as the input of another imo-vmdb
installation.  The raw ``imported_*`` tables are intentionally
excluded.

.. code-block:: python

   import sqlite3
   import imo_vmdb

   src = imo_vmdb.DBAdapter({"database": "/path/to/vmdb.db"})

   # Export to a portable SQLite file:
   dst = sqlite3.connect("/tmp/snapshot.sqlite")
   imo_vmdb.export_db(src, dst)
   dst.close()

.. autoclass:: imo_vmdb.CSVImporter
   :members:

Importing data
~~~~~~~~~~~~~~

:class:`~imo_vmdb.SessionImporter` is a programmatic alternative to CSV files
when you need to persist a complete observation session (with its rates and
magnitudes) directly from Python.  The caller controls the transaction:

.. code-block:: python

   from datetime import datetime
   import imo_vmdb

   db = imo_vmdb.DBAdapter({"database": "/path/to/vmdb.db"})

   session = imo_vmdb.SessionImport(
       id=12345,
       latitude=52.0,
       longitude=13.4,
       country="DE",
       location_name="Berlin",
       rates=(
           imo_vmdb.RateImport(
               id=700001,
               session_id=12345,
               shower="PER",
               period_start=datetime(2025, 8, 12, 22, 0, 0),
               period_end=datetime(2025, 8, 12, 23, 0, 0),
               t_eff=1.0,
               f=1.0,
               lim_magn=6.2,
               method="C",
               freq=17,
           ),
       ),
   )

   cur = db.cursor()
   imp = imo_vmdb.SessionImporter(cur)
   try:
       imp.upload(session)  # raises DuplicateSessionError if session already exists
       db.commit()
   except Exception:
       db.rollback()
       raise

Use ``upload(..., replace=True)`` to overwrite an existing session, or
:meth:`~imo_vmdb.SessionImporter.delete` to remove one.  Call
:func:`~imo_vmdb.normalize` afterwards to make the data visible in the
normalized tables (``obs_session``, ``rate``, ``magnitude``).  Log verbosity
can be adjusted via ``logging.getLogger("imo_vmdb").setLevel(...)``.

.. autoclass:: imo_vmdb.SessionImporter
   :members:

.. autoclass:: imo_vmdb.SessionImport
   :members:

.. autoclass:: imo_vmdb.RateImport
   :members:

.. autoclass:: imo_vmdb.MagnitudeImport
   :members:

.. autoexception:: imo_vmdb.DuplicateSessionError

Service classes
---------------

Each service class wraps a :class:`~imo_vmdb.DBAdapter` connection and
exposes the queries available for one entity.  The ``query`` method
returns the matching list (with optional pagination/total), ``by_id`` /
``by_code`` return a single record (or ``None``).

.. autoclass:: imo_vmdb.RateService
   :members:

.. autoclass:: imo_vmdb.MagnitudeService
   :members:

.. autoclass:: imo_vmdb.SessionService
   :members:

.. autoclass:: imo_vmdb.ShowerService
   :members:

.. autoclass:: imo_vmdb.StatsService
   :members:

Filter types
------------

.. autoclass:: imo_vmdb.RateFilter
   :members:

.. autoclass:: imo_vmdb.MagnitudeFilter
   :members:

.. autoclass:: imo_vmdb.SessionFilter
   :members:

Result types
------------

.. autoclass:: imo_vmdb.Shower
   :members:

.. autoclass:: imo_vmdb.Session
   :members:

.. autoclass:: imo_vmdb.Rate
   :members:

.. autoclass:: imo_vmdb.Magnitude
   :members:

.. autoclass:: imo_vmdb.MagnitudeDetail
   :members:

.. autoclass:: imo_vmdb.Radiant
   :members:

.. autoclass:: imo_vmdb.Rates
   :members:

.. autoclass:: imo_vmdb.Magnitudes
   :members:

.. autoclass:: imo_vmdb.Sessions
   :members:

.. autoclass:: imo_vmdb.StatsMeta
   :members:

.. autoclass:: imo_vmdb.ShowerStat
   :members:

.. autoclass:: imo_vmdb.CountryStat
   :members:

.. autoclass:: imo_vmdb.YearStat
   :members:

WSGI deployment
---------------

The web UI and REST API can be hosted under any WSGI server using the
public app factory ``imo_vmdb.httpd.wsgi_app``.  Configuration is read
from the ``IMO_VMDB_CONFIG`` environment variable (path to an INI file)
or directly from ``IMO_VMDB_*`` variables (see :ref:`setup`).

.. autofunction:: imo_vmdb.httpd.wsgi_app

Example using Gunicorn (install with ``pip install "imo-vmdb[web]"``):

.. code-block:: bash

    # With a config file:
    IMO_VMDB_CONFIG=config.ini \
        gunicorn --workers 1 --threads 4 \
        --bind 127.0.0.1:8000 "imo_vmdb.httpd:wsgi_app()"

    # Without a config file:
    IMO_VMDB_DATABASE_DATABASE=./vmdb.db \
        gunicorn --workers 1 --threads 4 \
        --bind 127.0.0.1:8000 "imo_vmdb.httpd:wsgi_app()"

.. warning::

   Always use ``--workers 1``.  The job manager stores job state in-process;
   multiple workers would make jobs invisible across processes, breaking status
   polling and log streaming.
