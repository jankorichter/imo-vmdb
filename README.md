# imo-vmdb

*imo-vmdb* imports data from the
[Visual Meteor Database (VMDB)](https://www.imo.net/members/imo_vmdb/)
of the [International Meteor Organization (IMO)](https://www.imo.net/)
into a relational SQL database.

The data is enriched with computed properties (radiant positions, sun/moon position and
illumination) and validated for plausibility.
No analysis is performed by the tool itself — the database is the output.

For full documentation see <https://imo-vmdb.readthedocs.io/en/latest/>.

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

**Run the web UI locally:**

```bash
poetry run python -m imo_vmdb web_server -c config.ini
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
