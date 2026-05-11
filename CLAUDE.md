# CLAUDE.md

## Project Overview

imo-vmdb imports meteor observation data from the IMO's Visual Meteor Database (VMDB) CSV files into a relational SQL database (SQLite, PostgreSQL, or MySQL). It enriches records with computed astronomical properties (radiant positions, sun/moon data) during a normalization step. Users access the processed data via the public Python API, the REST interface (`/api/v1`), the CLI commands, or the Web UI. Python API and REST are aimed at developers; CLI and Web UI at end users.

## Architecture

### Two-tier pipeline (core invariant)

Raw CSV data is stored in `imported_*` tables untouched. The `normalize` command then derives the final data into clean tables. These two stages must remain separate — never write directly to normalized tables during import.

| Stage | Tables |
|---|---|
| Raw import | `imported_session`, `imported_rate`, `imported_magnitude` |
| Normalized | `obs_session`, `rate`, `magnitude`, `magnitude_detail`, `rate_magnitude` |
| Reference data | `shower`, `radiant` |

### Layers

| Layer | Path | Purpose |
|---|---|---|
| CLI entry | `imo_vmdb/__main__.py` | Dispatches to command modules |
| Commands | `imo_vmdb/command/` | 6 CLI commands (see below) |
| CSV import | `imo_vmdb/csv_import/` | `CsvParser` base class + subclasses per file type |
| Normalizer | `imo_vmdb/normalizer/` | 3 normalization passes + rate-magnitude linking, Astropy |
| Domain models | `imo_vmdb/model/` | Shower/Radiant/Sky, coordinate calculations |
| DB layer | `imo_vmdb/db.py` | `DBAdapter` wrapping SQLite/PostgreSQL/MySQL |
| Query layer | `imo_vmdb/query.py` | Frozen dataclasses + query functions |
| REST API | `imo_vmdb/restapi.py` | Flask blueprint at `/api/v1` |
| Web UI | `imo_vmdb/webui/` | Routes, `JobManager`, HTML templates |
| HTTP server | `imo_vmdb/httpd.py` | Flask app factory + `main()` entry point |
| Public Python API | `imo_vmdb/__init__.py` | `__all__` exports — this is the stable API surface |

## Audiences

The project documentation serves three distinct roles. Keep their docs separate.

| Role | Tools | Docs live in |
|---|---|---|
| **User** — end-user of the software | `python -m imo_vmdb`, Docker image `ghcr.io/jankorichter/imo-vmdb` | `docs/` |
| **Developer** — develops this software itself | `make`, `poetry`, `ruff`, `pytest`, `docker compose` | `README.md`, `CLAUDE.md` |
| **Programmer** — uses the public Python API and REST API | `pip install imo-vmdb`, Gunicorn + `imo_vmdb.httpd:wsgi_app` | `docs/` (especially `api.rst`, `rest_api.rst`) |

**Hard rule**: developer-only tools (`poetry`, `make`, `ruff`, `pytest`, `docker compose`, source-tree git workflows) must not appear anywhere under `docs/`. Users install via pip or Docker; programmers via pip. Only README.md and CLAUDE.md describe the developer setup.

## Common Commands

```bash
make            # lint + test + docs + build
make review     # lint + test + docs (no build)
make test       # pytest
make lint       # ruff check + ruff format --check

# Auto-fix linting
poetry run ruff check --fix .
poetry run ruff format .

# CLI
poetry run python -m imo_vmdb <command>
# Commands: initdb, import_csv, normalize, cleanup, export, web_server

# Start web server (serves Web UI at / and REST API at /api/v1)
poetry run python -m imo_vmdb web_server -c config.ini
# Without config file:
IMO_VMDB_DATABASE_DATABASE=./data/vmdb.db poetry run python -m imo_vmdb web_server
# → http://127.0.0.1:8000
```

## Configuration

Config is read from an INI file (`[database]`, `[logging]`, `[webui]` sections) or environment variables with the `IMO_VMDB_` prefix. Environment variables override the config file.

Minimum required: `IMO_VMDB_DATABASE_DATABASE` (SQLite path or DB-URI).

Details: `docs/setup.rst`, `imo_vmdb/command/__init__.py` (`config_factory`).

## Testing

- All tests use **SQLite in-memory / temp files** — no PostgreSQL or MySQL in the test suite.
- Flask tests use the built-in test client — no server needs to start.
- Key fixtures in `tests/conftest.py`: `seeded_db`, `observation_db`, `client`, `obs_client`, `no_db_client`.
- Most fixtures are `function`-scoped; HTTP app fixtures are `session`-scoped.

```bash
poetry run pytest
```

## Documentation (for doc authors)

Sources are in `docs/*.rst`. The built HTML is embedded in the Python package under `imo_vmdb/built_docs/`.

```bash
poetry install --extras docs
poetry run sphinx-build -b html docs imo_vmdb/built_docs
```

`imo_vmdb/data/openapi.yaml` is the authoritative source for the REST API contract. It is shipped as package data, served live at `/api/v1/openapi.yaml`, and referenced from `docs/rest_api.rst` via a Sphinx `:download:` directive.

## Key Design Patterns

**DB dialect abstraction** — `DBAdapter._convert_stmt()` (internal, not part of the public API) translates `%(name)s` placeholders to the format expected by each supported SQL database, and `DBAdapter._year_expr()` builds the per-dialect year-extraction expression. Always use `%(name)s`-style parameters in SQL; never write dialect-specific SQL directly.

**CSV parsing** — add a new file type by subclassing `CsvParser` (`imo_vmdb/csv_import/`), declaring `_required_columns`, and implementing `parse_row()`.

**Public API** — only symbols exported from `imo_vmdb/__init__.py` are public. Changes there require documentation updates.

**Query results are frozen dataclasses** — do not modify them in place.

**Astronomical calculations happen at normalize time** — `imo_vmdb/model/sky.py` (Astropy) is called during normalization, not during queries.
