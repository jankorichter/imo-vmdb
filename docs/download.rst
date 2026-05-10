.. _download:

Database download
=================

The web server exposes a single binary download endpoint at
``/download/db`` that returns a snapshot of the current database as a
SQLite file.  The endpoint sits outside the REST API on purpose: REST
endpoints under ``/api/v1`` always return structured JSON, while
``/download/db`` is a one-off, self-contained file that can be saved,
shared, and re-used directly with imo-vmdb.

The endpoint is available regardless of whether the Web UI is enabled —
it only requires a configured ``[database]`` section.

.. _download-db:

GET /download/db
----------------

Returns the entire database (normalized observations and reference
data, excluding the raw ``imported_*`` tables) as a SQLite file
named ``imo_vmdb.sqlite``.  Schema and field names match a regular
imo-vmdb database, so the file can be opened by any SQLite client and
used as the input of another imo-vmdb installation::

    curl -OJ http://127.0.0.1:8000/download/db
    sqlite3 imo_vmdb.sqlite ".tables"
    IMO_VMDB_DATABASE_DATABASE=imo_vmdb.sqlite imo-vmdb export rate

If the server is started without a ``[database]`` section, the
endpoint returns ``503 Service Unavailable``.

The same export is available offline through the
:ref:`CLI <db-export>` and programmatically through the
:ref:`Python API <api>` (:func:`imo_vmdb.export_db`).
