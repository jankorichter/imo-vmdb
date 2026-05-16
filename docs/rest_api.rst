.. _rest-api:

REST API
========

*imo-vmdb* provides a read-only HTTP API that exposes the normalised database
content as JSON.
Any HTTP client can query the API without a direct database connection.

The REST API is served by the ``web_server`` command and is always enabled.
The browser-based control panel (Web UI) is opt-in and runs on the same
server when explicitly requested.

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
     - Rate observations (with pagination, sorting, field selection)
   * - ``/rates/{id}``
     - GET
     - Single rate observation
   * - ``/magnitudes``
     - GET
     - Magnitude observations (with pagination, sorting, field selection)
   * - ``/magnitudes/{id}``
     - GET
     - Single magnitude observation
   * - ``/sessions``
     - GET
     - Observation sessions
   * - ``/sessions/{id}``
     - GET
     - Single observation session
   * - ``/showers``
     - GET
     - Meteor shower reference data
   * - ``/showers/{iau_code}``
     - GET
     - Single shower
   * - ``/showers/{iau_code}/radiants``
     - GET
     - Radiant positions for a shower (sorted by month/day)
   * - ``/showers/active``
     - GET
     - Showers active on a given date (default: today UTC)
   * - ``/stats/meta``
     - GET
     - Database scope summary (counts, covered date range)
   * - ``/stats/by-shower``
     - GET
     - Per-shower aggregate counts
   * - ``/stats/by-country``
     - GET
     - Per-country aggregate counts
   * - ``/stats/by-year``
     - GET
     - Per-year aggregate counts
   * - ``/health``
     - GET
     - Liveness/readiness probe; returns ``200 OK`` when the database is
       reachable, ``503`` otherwise. Suitable for load balancers and
       Kubernetes probes.
   * - ``/openapi.yaml``
     - GET
     - Full OpenAPI 3.1 specification (YAML)
   * - ``/openapi.json``
     - GET
     - Full OpenAPI 3.1 specification (JSON)

All filter parameters are optional.
An unfiltered request returns *all* records; combine parameters as needed.

Pagination and totals
---------------------

The list endpoints (``/rates``, ``/magnitudes``, ``/sessions``) accept
optional ``limit`` and ``offset`` query parameters and **always** return
the unpaginated total count in the ``X-Total-Count`` response header::

    /api/v1/rates?shower=PER&limit=50&offset=100

To obtain only the count without any rows, use ``limit=0``::

    /api/v1/rates?shower=PER&limit=0

The response will have an empty ``observations`` array; the actual count
is in the ``X-Total-Count`` header.

Sorting
-------

The list endpoints accept ``order_by`` (one of ``id``, ``period_start``,
``period_end``, ``sl_start``, ``lim_magn``) and ``order`` (``asc`` or
``desc``)::

    /api/v1/rates?order_by=period_start&order=desc

Field selection
---------------

Use ``fields`` with a comma-separated list to restrict the response
shape::

    /api/v1/rates?fields=id,shower,period_start,freq

Unknown field names result in HTTP 400.

Sporadic meteors
----------------

By convention, sporadic meteors are identified by the code ``SPO``.
They carry no shower assignment and the ``shower`` field is ``null``
in the API response. To filter for sporadic meteors, pass ``shower=SPO``::

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
:download:`openapi.yaml <../imo_vmdb/data/openapi.yaml>`.

The live server also serves the same file at ``/api/v1/openapi.yaml``.
Open either in any OpenAPI-compatible tool such as
`Swagger UI <https://swagger.io/tools/swagger-ui/>`_ or
`Redoc <https://redocly.com/redoc>`_.

For running the server, see :ref:`cli` (Python) and :ref:`docker` (Docker).
For enabling the optional browser-based control panel, see :ref:`webui`.
