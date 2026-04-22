.. _rest-api:

REST API
========

*imo-vmdb* provides a read-only HTTP API that exposes the normalised database
content as JSON.
Any HTTP client can query the API without a direct database connection.

Base URL
--------

All endpoints are served under ``/api/v1``.
With the default server configuration the full base URL is::

    http://localhost:8000/api/v1

Endpoints
---------

.. list-table::
   :header-rows: 1
   :widths: 30 10 60

   * - Path
     - Method
     - Description
   * - ``/rates``
     - GET
     - Rate observations
   * - ``/magnitudes``
     - GET
     - Magnitude observations
   * - ``/showers``
     - GET
     - Meteor shower reference data
   * - ``/openapi.yaml``
     - GET
     - Full OpenAPI 3.1 specification

All filter parameters are optional.
An unfiltered request returns *all* records; combine parameters as needed.

Sporadic meteors
----------------

By convention, sporadic meteors are identified by the code ``SPO``.
They carry no shower assignment and the ``shower`` field is ``null``
in the API response.
To filter for sporadic meteors, pass ``shower=SPO``::

    /api/v1/rates?shower=SPO

.. important::
   ``shower=SPO`` is the query filter for sporadics.
   The API returns ``"shower": null`` for the same records —
   ``SPO`` never appears in the response.

Repeating a query parameter with the same name is valid HTTP (RFC 3986)
and the standard way to pass multiple values.
The following example requests both Perseids *and* sporadic meteors::

    /api/v1/rates?shower=PER&shower=SPO

Related data via ``include``
----------------------------

Pass ``include=sessions`` and/or ``include=magnitudes`` to receive session
and magnitude-detail data alongside observations::

    /api/v1/rates?shower=PER&include=sessions,magnitudes

The response then contains ``sessions`` and ``magnitudes`` arrays in addition
to ``observations``.

Examples
--------

Perseids around their peak, filtered by solar longitude::

    /api/v1/rates?shower=PER&sl_min=139.0&sl_max=141.0

Combined with a time period and a minimum limiting magnitude::

    /api/v1/rates?shower=PER&period_start=2018-08-10&period_end=2018-08-14&sl_min=138.0&sl_max=142.0&lim_magn_min=5.5

For the complete field reference, see :ref:`fields`.

Including session data in the same request::

    /api/v1/rates?shower=PER&sl_min=139.0&sl_max=141.0&include=sessions

API specification
-----------------

The complete endpoint and schema reference is available as an
`OpenAPI 3.1 <https://spec.openapis.org/oas/v3.1.0>`_ document:
:download:`openapi.yaml`.

The live server also serves the same file at ``/api/v1/openapi.yaml``.
Open either in any OpenAPI-compatible tool such as
`Swagger UI <https://swagger.io/tools/swagger-ui/>`_ or
`Redoc <https://redocly.com/redoc>`_.

For running the server, see :ref:`webui` and :ref:`docker`.
