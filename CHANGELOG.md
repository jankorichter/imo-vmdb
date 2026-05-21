# Changelog

## [2.1.0] — [unreleased]

### Changed

- **CSV import — consistent column names via aliases.**
  `_required_columns` on every `CsvParser` subclass is now a list of
  alias groups (`tuple[tuple[str, ...], ...]`).  The first name in each
  group is the canonical name, matching the export column names and the
  REST API; the remaining names are kept for backward compatibility with
  the original IMO CSV files.  New protected classmethods
  `_is_responsible()` and `_resolve_column_mapping()` handle group-based
  header matching and canonical renaming.  If a CSV file supplies two
  synonymous column names (e.g. both `session id` and `session_id`), the
  import is rejected with a clear error message.
- **Shower reimport export** (`--reimport`) now uses `dec` instead of
  `de`; `de` remains accepted as an import alias, so old exported files
  stay re-importable.

## [2.0.0] — 2026-05-19

### Added

- **Web UI** — small "Database Contents" panel at the top of the
  control panel showing the totals for the imported (raw CSV) stage
  and the normalized stage: sessions, rate observations (with total
  meteors and covered date range), and magnitude observations (with
  total meteors and covered date range).  Auto-refreshes after each
  background job completes.
- **REST API (`/api/v1/stats/meta`)** — response gains eleven
  backward-compatible fields: `imported_sessions`, `imported_rates`,
  `imported_magnitudes`, `rate_meteors`, `magnitude_meteors`,
  `imported_rate_meteors`, `imported_magnitude_meteors`,
  `rate_period_start`, `rate_period_end`, `magnitude_period_start`,
  `magnitude_period_end`.  The imported-magnitude meteor total is
  computed from the JSON `magn` column on `imported_magnitude`.
  Existing `period_start`/`period_end` remain the union of the two
  per-table ranges.

### BREAKING

- **Datetime handling end-to-end; strict ISO 8601 on the REST wire.**
  `period_start` / `period_end` are `datetime.datetime` from the DB
  read to the REST serialiser:
  - SQLite connections opt into `sqlite3.PARSE_DECLTYPES` and the
    project registers explicit adapter/converter callables for
    `datetime.datetime` ↔ `"timestamp"` (replacing the Python
    3.12-deprecated built-ins).  PostgreSQL and MySQL drivers return
    `datetime` natively.
  - Normalizer and CSV importer code paths bind raw `datetime`
    objects to INSERT parameters instead of pre-formatting with
    `isoformat(sep=" ")`.
  - `Rate.period_start`, `Rate.period_end`,
    `Magnitude.period_start`, `Magnitude.period_end`, and every
    `StatsMeta.*period_*` field are now `datetime.datetime` /
    `datetime.datetime | None` on the Python API surface.  Filter
    dataclasses (`RateFilter`, `MagnitudeFilter`, `SessionFilter`)
    and `StatsService.by_*` method signatures match.
  - REST API input is strict: `period_start` / `period_end` must be
    exactly `YYYY-MM-DDTHH:MM:SS` (UTC implied by IMO convention; no
    timezone marker).  Space separator, date-only, trailing `Z`, and
    `±HH:MM` offsets are rejected with HTTP 400 and a message
    `"Invalid datetime: expected YYYY-MM-DDTHH:MM:SS, got '…'"`.
  - REST API output is strict: every `period_*` field is serialised
    via `datetime.isoformat()` (`YYYY-MM-DDTHH:MM:SS`, no timezone
    marker) — regardless of DB dialect.
  - Legacy databases (1.x, space-separated DB strings) remain
    readable via the `fromisoformat()`-based converter.  Re-importing
    under 2.0.0 (which `initdb` requires anyway for the unrelated
    schema rebuilds) yields ISO-T storage going forward.
  - Clients that send anything other than the strict T-format
    (notably older vismeteor releases) need to update — tracked as a
    separate vismeteor follow-up.

- **`rate_magnitude` table dropped; its payload moves onto `rate`.**
  The 1:1 sidecar was redundant — `magn_id` and the former
  `rate_magnitude.equals` boolean (renamed to `magn_solo`) become
  direct columns on `rate`.
  - Schema: `rate.magn_id INTEGER NULL` (FK → `magnitude(id)`,
    `ON DELETE SET NULL`) and `rate.magn_solo BOOLEAN NULL`
    (`true` when this rate is the solo contributor to its magnitude;
    `false` when the magnitude aggregates this rate with others;
    `NULL` when `magn_id IS NULL`).
  - `Rate` dataclass and the REST `RateObservation` schema gain
    `magn_solo`.  `Rate.magn_id` is unchanged.
  - Normalizer: `create_rate_magn` now `UPDATE rate SET magn_id = …,
    magn_solo = …` instead of writing the sidecar.
  - Query layer: `_RATE_SELECT` reads `rate.magn_id` and
    `rate.magn_solo` directly.
  - Export surfaces: `rate_magnitude` is removed from
    `_EXPORTABLE_DB_TABLES`, so the CLI command, Web UI button, and
    `export_db()` SQLite snapshot all stop including it.
    `export_table(db, "rate_magnitude")` raises `ValueError` (the
    helper now validates against `_EXPORTABLE_DB_TABLES`, so
    `imported_*` tables are likewise rejected — they were already
    absent from the CLI surface).
  - Migration: no automatic migration — run `imo-vmdb initdb` and
    re-import + re-normalize (same workflow as the 1.8.0 BREAKING
    schema rename).
- **Per-class frequencies renamed from `magnitudes` to `magnitude_details`.**
  The old name was misleading — it carried `MagnitudeDetail` rows, not
  magnitude observations.  The name `magnitudes` is now consistently
  used for full `Magnitude` observations across the REST API and the
  Python data classes.

  - REST API:
    - `/rates?include=magnitudes` → full `MagnitudeObservation` rows.
      For per-class frequencies, use `?include=magnitude_details`.
    - `/magnitudes?include=magnitudes` → HTTP 400.  Use
      `?include=magnitude_details`.
  - Python API:
    - `Rates.magnitudes` is now `list[Magnitude] | None`; new
      `Rates.magnitude_details: list[MagnitudeDetail] | None`.
    - `Magnitudes.magnitudes` is removed; use
      `Magnitudes.magnitude_details`.
    - `RateFilter.include_magnitudes` now toggles the full observations;
      new `RateFilter.include_magnitude_details` for the old behaviour.
    - `MagnitudeFilter.include_magnitudes` is removed; use
      `MagnitudeFilter.include_magnitude_details`.

### Added

- **REST API (`/api/v1/sessions`)** — filter and include parity with
  `/rates` and `/magnitudes`:
  - New observation-level filters, resolved via EXISTS on `rate` and
    `magnitude`: `shower` (repeatable; `SPO` for sporadics), `sl_min`,
    `sl_max`, `lim_magn_min`, `lim_magn_max`.
  - New `include` parameter with values `rates` and `magnitudes`.
    Included observations are restricted by the same filters and to the
    session IDs in the response page.  Per-class frequencies are
    intentionally not exposed here — use
    `/magnitudes?session_id=…&include=magnitude_details`.
- **Python API** — `SessionFilter` gains `showers`, `sl_min`, `sl_max`,
  `lim_magn_min`, `lim_magn_max`, `include_rates`, `include_magnitudes`.
  `Sessions` gains `rates` and `magnitudes` attributes.

### Changed

- **REST API (`/api/v1/rates`)** — `?include=magnitude_details` no longer
  requires `?include=magnitudes`.  Each detail row's `id` matches
  `Rate.magn_id`, which is enough to attribute frequencies to rates.

### Fixed

- **Security** — bumped transitive `urllib3` to `>= 2.7.0` in
  `poetry.lock`, addressing two open Dependabot advisories (sensitive
  headers forwarded across origins in proxied low-level redirects;
  decompression-bomb safeguards bypassed in parts of the streaming API).
  `requests`, `idna`, `click`, and `astropy-iers-data` picked up minor
  refresh bumps in the same resolution pass.

## [1.8.0] — 2026-05-16

### BREAKING

- **DB schema** — columns renamed for clarity and consistency:
  - `obs_session.city`, `imported_session.city` → `location_name`
  - `rate.lim_mag`, `magnitude.lim_mag` → `lim_magn`

  Existing databases are not migrated automatically. Run
  `imo-vmdb initdb` and re-import your CSVs.
- **Python API** — dataclass fields renamed:
  - `Session.city` → `Session.location_name`
  - `Rate.lim_mag`, `Magnitude.lim_mag` → `lim_magn`

  The sortable field name in `RateFilter.order_by` /
  `MagnitudeFilter.order_by` changes from `"lim_mag"` to `"lim_magn"`.
- **REST API (`/api/v1/`)** — response field names follow the Python API:
  - `Session.city` → `Session.location_name`
  - `Rate.lim_mag`, `Magnitude.lim_mag` → `lim_magn`
  - `order_by=lim_mag` → `order_by=lim_magn` for `/rates` and `/magnitudes`.

  The `lim_magn_min` / `lim_magn_max` query parameters are unchanged
  (they already used the new spelling).

## [1.7.2] — 2026-05-11

### Changed

- **`DBAdapter`** — the dialect helpers `convert_stmt()` and `year_expr()`
  are now private (`_convert_stmt()`, `_year_expr()`) and are no longer part
  of the public Python API. They were internal SQL placeholder / expression
  helpers that application code never needed.

## [1.7.1] — 2026-05-10

### Fixed

- **`/api/v1/openapi.{yaml,json}`** — no longer returns `404` in installed
  environments (pipx, pip, Docker); the spec now ships as package data.

## [1.7.0] — 2026-05-10

#### Added

- **SQLite database export** — share or back up a complete imo-vmdb
  database as a single SQLite file that uses the same schema as a
  regular install and can be opened directly with imo-vmdb. Available
  via the new CLI target `imo-vmdb export db -o snapshot.sqlite`, the
  *Export DB* button in the Web UI, and the HTTP endpoint
  `/download/db` (served regardless of whether the Web UI is enabled).
  The raw `imported_*` tables are intentionally excluded.

- **`imo_vmdb.export_db(src_db_conn, dst_conn)`** — copies a database
  into an externally-owned `sqlite3.Connection` (file-backed or
  `:memory:`). Schema and lifecycle of the destination are controlled
  by the caller.

## [1.6.0] — 2026-05-10

### For users

#### Changed

- **`imo-vmdb` console script** — installs as a single entry point so the
  CLI can be invoked as `imo-vmdb <command>` instead of
  `python -m imo_vmdb <command>`. Both forms continue to work.
- **pipx installation** — `pipx install imo-vmdb` is now supported as a
  global install path alongside `pip install imo-vmdb`.
- **Docker image** — now serves the application via Gunicorn
  (`imo_vmdb.httpd:wsgi_app`) instead of the Flask development server, so
  the published image at `ghcr.io/jankorichter/imo-vmdb` is production-ready
  out of the box.
- **BREAKING:** `web_server` no longer starts the Web UI by default — only
  the REST API is served. Pass `--enable-webui`, set
  `IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true`, or add `enable_webui = true`
  under the `[webserver]` section to restore the previous behaviour.
- **BREAKING:** Configuration section renamed from `[webui]` to
  `[webserver]`. Affects `port`, `host`, `upload_dir`, and the new
  `enable_webui` key.
- **BREAKING:** Environment variables renamed
  `IMO_VMDB_WEBUI_*` → `IMO_VMDB_WEBSERVER_*`
  (`PORT`, `HOST`, `UPLOAD_DIR`, plus the new `ENABLE_WEBUI` and `THREADS`).

#### Fixed

- **MagnitudeNormalizer** — database write errors during normalization now
  discard the offending record instead of aborting the run, mirroring
  `RateNormalizer`'s behaviour.

#### Documentation

- **CLI** — `import_csv`'s `--permissive` and `--repair` modes are now
  fully described, including which validation steps each mode relaxes.
- ReadTheDocs default version pinned to `stable`
  (<https://imo-vmdb.readthedocs.io/en/stable/>).

### For programmers

#### Python API — Added

- **Service classes with typed results** — `RateService`,
  `MagnitudeService`, `SessionService`, `ShowerService`, `StatsService`,
  each exposing a `.query(...)` method returning frozen dataclasses
  (`Rates`, `Magnitudes`, `Sessions`, `Shower`, `ShowerStat`,
  `CountryStat`, `YearStat`, `StatsMeta`, …) and accepting filter
  dataclasses (`RateFilter`, `MagnitudeFilter`, `SessionFilter`).
- **`DBAdapter`, `DBException`** are now part of the public API
  (`from imo_vmdb import DBAdapter, DBException`), so callers no longer
  need to reach into `imo_vmdb.db`.
- **`DBAdapter.ping()`** — issues `SELECT 1` for liveness/readiness
  checks; raises `DBException` on driver errors. Used by `/api/v1/health`.
- **`imo_vmdb.httpd.wsgi_app`** — public WSGI factory for hosting the
  Web UI and REST API behind Gunicorn or any other WSGI server.
- **Type hints** added throughout the public API surface.

#### Python API — BREAKING

- The free functions `query_showers`, `query_rates`, and `query_magnitudes`
  have been removed. Use the corresponding `*Service.query(...)` methods
  instead. Migration:
  - `query_rates(db, ...)` → `RateService(db).query(RateFilter(...))`
  - `query_magnitudes(db, ...)` → `MagnitudeService(db).query(MagnitudeFilter(...))`
  - `query_showers(db)` → `ShowerService(db).query()`

#### REST API (`/api/v1/`) — Added

- Detail endpoints by ID: `/rates/<id>`, `/magnitudes/<id>`,
  `/sessions/<id>`, `/showers/<iau_code>`, `/showers/<iau_code>/radiants`.
- New collections: `/sessions`, `/showers/active`.
- Statistics: `/stats/meta`, `/stats/by-shower`, `/stats/by-country`,
  `/stats/by-year`.
- Operational: `/health` (liveness/readiness), `/openapi.json`
  (alongside the existing `/openapi.yaml`).

### For developers

- **Ruff** is now the project's linter and formatter
  (`make lint`, `make review`); CI runs `ruff check` and
  `ruff format --check` on every push.
- Source-code docstrings added across the package; type hints added
  at service boundaries.

## [1.5.2] — 2026-05-02

### Fixed

- **Astropy 7.x compatibility** — deprecated `get_moon`/`get_sun` calls in
  `imo_vmdb/model/sky.py` replaced with `get_body`; `GeocentricMeanEcliptic`
  now uses explicit `equinox='J2000'`.
- **Idempotent import and normalization** — all CSV importers and the normalizer
  delete existing records before inserting, so import and normalization can be
  repeated without triggering database errors or producing duplicates.
- **Built wheel now includes documentation** — `imo_vmdb/built_docs` is built
  before packaging and embedded in both the wheel and sdist.

### Improved

- **Logging** — discarded observations are now reported uniformly as
  `session X: observation Y discarded - <reason>` via a new `_log_discard()`
  method in the base normalizer; CSV importer messages now follow
  `session X: ID Y: <message>` (rate/magnitude) or `ID X: <message>`
  (shower/radiant/session) throughout.

## [1.5.1] — 2026-04-25

### Fixed

- `docs/about.rst` — rewrote description to clarify imo-vmdb as a data preparation tool;
- `docs/cli.rst` — corrected "correction factor of the radiant altitude" to
  "radiant altitude with zenith attraction applied".
- `docs/fields.rst` — added entity relationship diagram.
- Web UI log — ERROR lines highlighted red, WARNING lines highlighted yellow.

## [1.5.0] — 2026-04-25

### Added

- **REST API** (`/api/v1/`) — query rate and magnitude observations via HTTP.
  Endpoints: `/rates`, `/magnitudes`, `/showers`, `/openapi.yaml`.
  Filters: shower code, period, solar longitude, limiting magnitude, sun/moon altitude.
  Optional sideloading of sessions and magnitude details via `include=` parameter.
- **Web UI** — browser-based control panel for all database operations
  (init, import, normalize, cleanup) with live log streaming via Server-Sent Events.
- **CSV export** — download any normalized table as a semicolon-delimited CSV file
  directly from the web UI or via `python -m imo_vmdb export <table>`.
  The `--reimport` flag exports showers and radiants in the original import format.
- **Docker support** — `Dockerfile` and `compose.yml` for container-based deployment.
  Docker image published to `ghcr.io/jankorichter/imo-vmdb`.
- **OpenAPI 3.1 specification** — `docs/openapi.yaml`, also served live at `/api/v1/openapi.yaml`.

### Changed

- CLI command `webui` renamed to `web_server` (starts both the web UI and the REST API).
- Unified CLI dispatch in `__main__.py` — all commands use a single dispatch table.
- Documentation fully restructured: new pages `setup`, `cli`, `webui`, `rest_api`, `fields`.
  Old pages `install`, `docker`, `db`, `import`, `normalizing` removed.

### Fixed

- Comments in `imo_vmdb/**/*.py` translated to English.


## [1.4.0] — 2024-01-13

Initial public release.
