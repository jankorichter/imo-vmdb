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
   :members: cleanup, initdb, normalize, export_table,
             query_showers, query_rates, query_magnitudes

.. autoclass:: imo_vmdb.CSVImporter
   :members:

Filter types
------------

.. autoclass:: imo_vmdb.RateFilter
   :members:

.. autoclass:: imo_vmdb.MagnitudeFilter
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

.. autoclass:: imo_vmdb.Rates
   :members:

.. autoclass:: imo_vmdb.Magnitudes
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
