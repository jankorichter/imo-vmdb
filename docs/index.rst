Introduction
============

*imo-vmdb* imports, normalizes, and enriches visual meteor observation data
from the `Visual Meteor Database (VMDB) <https://www.imo.net/members/imo_vmdb/>`_.
Enriched observations can be accessed via a REST API, CSV export, or direct
database connection.

The tool can be used in two ways:

- **Docker** (recommended for most users): run the web-based control panel
  without any local Python installation — see :ref:`setup`.
- **Python package**: use the command-line interface directly via Poetry —
  see :ref:`setup`.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   about
   setup
   cli
   webui
   rest_api

.. toctree::
   :maxdepth: 1
   :caption: Reference:

   csv
   fields
   api
