Introduction
============

*imo-vmdb* is a bridge between raw IMO visual meteor observation data and the
tools you use to analyse it.  It imports CSV files downloaded from the
`IMO VMDB <https://www.imo.net/members/imo_vmdb/>`_, enriches each record with
computed astronomical values (radiant positions, solar longitude, limiting
magnitude corrections), and makes the results available via a REST API, a CSV
export, or the :ref:`Python API <api>` (``imo_vmdb``).  The enriched data is
particularly useful in analysis environments that have no built-in astronomical
algorithms — for example the R package
`vismeteor <https://CRAN.R-project.org/package=vismeteor>`_ on CRAN builds
directly on this API.

*imo-vmdb* prepares and delivers data.  It is not an analysis tool itself.

Install and run in two ways — see :ref:`setup` for details:

- **Python (pipx)**: recommended for most users; one command installs the CLI.
- **Docker**: no Python required; suited for server deployments.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   about
   setup
   cli
   webui
   rest_api
   download

.. toctree::
   :maxdepth: 1
   :caption: Reference:

   api
   csv
   fields
