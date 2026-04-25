# Changelog

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
