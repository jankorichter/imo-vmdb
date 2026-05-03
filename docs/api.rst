.. _api:

Python API
==========

*imo-vmdb* exposes two Python APIs that can be used independently of any web
framework.

The **core API** (``imo_vmdb``) covers importing, normalising, cleaning up,
and exporting data.  The **server API** (``imo_vmdb.server``) adds
framework-agnostic building blocks for querying observations and running
long-running jobs — the same logic that the built-in Flask application uses
internally.  Python developers who prefer FastAPI, Django, or
any other framework can import these building blocks directly and build their
own HTTP layer on top.

Core API (``imo_vmdb``)
-----------------------

.. automodule:: imo_vmdb
   :members: cleanup, initdb, normalize, export_table, CSVImporter

Server API (``imo_vmdb.server``)
---------------------------------

The server API provides two groups of functionality:

- **Job management** — run database operations asynchronously in a background
  thread and stream log output to any consumer.
- **Data queries** — query rate and magnitude observations with typed filter
  objects instead of raw SQL.

All classes and functions are importable directly from ``imo_vmdb.server``::

    from imo_vmdb.server import JobManager, RateFilter, query_rates

Job management
~~~~~~~~~~~~~~

.. autoclass:: imo_vmdb.server.JobManager
   :members:

Query filters
~~~~~~~~~~~~~

.. autoclass:: imo_vmdb.server.RateFilter
   :members:

.. autoclass:: imo_vmdb.server.MagnitudeFilter
   :members:

Query functions
~~~~~~~~~~~~~~~

.. autofunction:: imo_vmdb.server.query_showers

.. autofunction:: imo_vmdb.server.query_rates

.. autofunction:: imo_vmdb.server.query_magnitudes

Example: querying without Flask
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following example queries rate observations directly from Python without
starting any HTTP server::

    from imo_vmdb.db import DBAdapter
    from imo_vmdb.server import RateFilter, query_rates, query_showers

    db_conn = DBAdapter({'database': '/path/to/imo_vmdb.db'})

    showers = query_showers(db_conn)
    print(f'{len(showers)} showers loaded')

    perseids = query_rates(db_conn, RateFilter(
        showers=['PER'],
        sl_min=139.0,
        sl_max=141.0,
        include_sessions=True,
    ))
    print(f'{len(perseids["observations"])} Perseid rate observations found')

    db_conn.close()
