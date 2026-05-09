# imo-vmdb

*imo-vmdb* imports data from the
[Visual Meteor Database (VMDB)](https://www.imo.net/members/imo_vmdb/)
of the [International Meteor Organization (IMO)](https://www.imo.net/)
into a relational SQL database.

The data is enriched with computed properties (radiant positions, sun/moon position and
illumination) and validated for plausibility.
The processed data is accessible via a public Python API, a REST interface, CLI commands,
and a Web UI.

For full documentation see <https://imo-vmdb.readthedocs.io/en/stable/>.

---

## Quick Start (Docker)

No Python required. Pull and run the web UI:

```bash
docker run --rm \
    -p 8000:8000 \
    -v ./data:/data \
    -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
    ghcr.io/jankorichter/imo-vmdb
```

Open <http://localhost:8000>.

---

## Developer Setup

**Prerequisites:** Python 3.10+, [Poetry](https://python-poetry.org/docs/#installation)

```bash
git clone https://github.com/jankorichter/imo-vmdb.git
cd imo-vmdb
poetry install
poetry run python -m imo_vmdb
```

**With documentation extras** (required to build Sphinx docs):

```bash
poetry install --extras docs
```

**Run the web UI and REST API locally:**

```bash
IMO_VMDB_DATABASE_DATABASE=./data/vmdb.db poetry run python -m imo_vmdb web_server
```

Opens the control panel at `http://localhost:8000`; the REST API is available at `http://localhost:8000/api/v1`.

**Test the production WSGI deployment:**

The production setup uses Gunicorn with `imo_vmdb.httpd:wsgi_app`. To verify locally:

```bash
poetry install --extras web
IMO_VMDB_DATABASE_DATABASE=./data/vmdb.db \
    poetry run gunicorn --workers 1 --threads 4 \
    --bind 127.0.0.1:8000 "imo_vmdb.httpd:wsgi_app()"
```

Always use `--workers 1` — see `docs/api.rst` for details.

**Run the linter:**

```bash
poetry run ruff check .
poetry run ruff format --check .
```

To auto-fix issues:

```bash
poetry run ruff check --fix .
poetry run ruff format .
```

**Run the test suite:**

```bash
poetry run pytest
```

No server needs to be started beforehand. The tests use Flask's built-in test
client, which calls the application directly in-process — no network, no port.
A temporary SQLite database is created automatically for each test run.

**Build Docker image locally:**

```bash
docker compose up --build
```

## Release

Releases are triggered by pushing a version tag. The GitHub Actions workflows in
`.github/workflows/` handle CI and publishing automatically:

- **`tests.yml`** — runs lint and tests on every push to any branch
- **`pypi.yml`** — builds the package and publishes it to PyPI (version tags only)
- **`docker.yml`** — builds and pushes the Docker image to GitHub Container Registry (version tags only)

Before tagging, build and verify the package locally:

```bash
make        # builds docs, then runs poetry build
```

Then tag and push:

```bash
git tag v1.x.y
git push origin v1.x.y
```
