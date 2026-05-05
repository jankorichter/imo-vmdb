.. _api:

Python API
==========

The ``imo_vmdb`` package provides a Python API that can be used independently
of any web framework or HTTP connection.  It covers importing, normalising,
cleaning up, exporting, and querying meteor observation data.

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
