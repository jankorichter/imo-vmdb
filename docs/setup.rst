.. _setup:

Setup
=====

*imo-vmdb* processes meteor observation data and stores the results in a
**database** — a structured file or service where data is kept permanently.
The software manages the database itself; you only need to tell it where to
store the data.

There are two ways to run *imo-vmdb*:

* **Docker** — no Python installation required; runs as a web application in
  your browser.  Recommended for most users.
* **Python** — install directly and use the command-line interface.  Suited
  for developers and scripted workflows.

Both options require choosing a database.  Read the next section first, then
follow the path that fits your setup.

.. _database-setup:

Database
--------

*imo-vmdb* supports three database systems. For most users, **SQLite** is
the right choice.

SQLite (recommended)
********************

SQLite stores all data in a single file on your computer — no database server,
no additional software, no user accounts.  You only provide a file path;
*imo-vmdb* creates and manages the file for you.

This is the default.  No extra packages are needed.

PostgreSQL and MySQL (advanced)
*******************************

PostgreSQL and MySQL are full database servers.  Setting them up requires
knowledge of database administration — creating users, databases, and managing
connections.  They make sense when:

* multiple people or applications need to access the data simultaneously,
* the data should be stored on a central server rather than a local file,
* you already operate a database server as part of your infrastructure.

If you are unsure, use SQLite.


.. _docker:

Docker
------

Docker lets you run *imo-vmdb* without installing Python or any other
programming tools.  It works by running the software in an isolated
*container* — think of it as a self-contained box that has everything
it needs built in.

Command Line
************

Starting the web UI::

    docker run --rm \
        -p 8000:8000 \
        -v /your/local/data:/data \
        -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
        -e IMO_VMDB_WEBSERVER_UPLOAD_DIR=/data/uploads \
        -e IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true \
        ghcr.io/jankorichter/imo-vmdb

The Web UI is opt-in.  Without ``IMO_VMDB_WEBSERVER_ENABLE_WEBUI=true`` the
container serves only the REST API at ``/api/v1``.

Replace ``/your/local/data`` with your data folder path.
Open ``http://localhost:8000`` in your browser.  Press ``Ctrl+C`` to stop.

Running individual commands::

    # Initialize the database
    docker run --rm \
        -v /your/local/data:/data \
        -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
        ghcr.io/jankorichter/imo-vmdb initdb

    # Import CSV files
    docker run --rm \
        -v /your/local/data:/data \
        -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
        -v /path/to/csv:/csv \
        ghcr.io/jankorichter/imo-vmdb import_csv /csv/observations-2024.csv

    # Normalize
    docker run --rm \
        -v /your/local/data:/data \
        -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
        ghcr.io/jankorichter/imo-vmdb normalize

All Environment Variables
*************************

.. list-table::
   :header-rows: 1
   :widths: 35 30 15

   * - Variable
     - Config equivalent
     - Default
   * - ``IMO_VMDB_DATABASE_DATABASE``
     - ``[database] database``
     - *(required)*
   * - ``IMO_VMDB_DATABASE_MODULE``
     - ``[database] module``
     - ``sqlite3``
   * - ``IMO_VMDB_DATABASE_HOST``
     - ``[database] host``
     - —
   * - ``IMO_VMDB_DATABASE_USER``
     - ``[database] user``
     - —
   * - ``IMO_VMDB_DATABASE_PASSWORD``
     - ``[database] password``
     - —
   * - ``IMO_VMDB_LOGGING_LEVEL``
     - ``[logging] level``
     - ``INFO``
   * - ``IMO_VMDB_WEBSERVER_UPLOAD_DIR``
     - ``[webserver] upload_dir``
     - system temp dir
   * - ``IMO_VMDB_WEBSERVER_HOST``
     - ``[webserver] host``
     - ``127.0.0.1`` (Dev), ``0.0.0.0`` (Gunicorn)
   * - ``IMO_VMDB_WEBSERVER_PORT``
     - ``[webserver] port``
     - ``8000``
   * - ``IMO_VMDB_WEBSERVER_THREADS``
     - *(Gunicorn only)*
     - ``4``
   * - ``IMO_VMDB_WEBSERVER_ENABLE_WEBUI``
     - ``[webserver] enable_webui``
     - ``false``

Environment variables work with any *imo-vmdb* installation — not just Docker.

Using a Config File
*******************

A configuration file can be used instead of, or in combination with,
environment variables.  If a file is provided it takes precedence::

    docker run --rm \
        -v /your/local/data:/data \
        ghcr.io/jankorichter/imo-vmdb initdb -c /data/config.ini

See the `Python`_ section below for the configuration file format.

----

Python
------

If you already have Python 3.10 or newer installed, *imo-vmdb* can be
installed in two equally supported ways: into a **virtual environment**
with ``pip``, or globally for the current user with **pipx**.  Both work
identically on macOS, Linux, and Windows.


**Virtual environment**

A virtual environment keeps *imo-vmdb* isolated from other Python packages
on your system::

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install imo-vmdb

Activate the environment with ``source .venv/bin/activate`` each time you
open a new terminal before running *imo-vmdb*.

Verify the installation::

    imo-vmdb

A short help text listing the available commands should appear.

**pipx**

`pipx <https://pipx.pypa.io/>`_ installs Python applications into their
own isolated environments and exposes their entry points as global
commands — no virtual environment to activate manually.  Install pipx
itself once (see the link above), then::

    pipx install imo-vmdb

The ``imo-vmdb`` command is now available globally::

    imo-vmdb --help

Quick start with SQLite
***********************

For SQLite, no configuration file is required.  Point *imo-vmdb* at a
file path via the ``IMO_VMDB_DATABASE_DATABASE`` environment variable —
the database file is created on first use.  Set the variable once for
the current shell session, then run the commands.

macOS / Linux (bash, zsh)::

    export IMO_VMDB_DATABASE_DATABASE=/path/to/vmdb.db

    imo-vmdb initdb
    imo-vmdb import_csv observations-2024.csv
    imo-vmdb normalize
    imo-vmdb web_server   # REST API at /api/v1; Web UI optional via --enable-webui

Windows PowerShell::

    $env:IMO_VMDB_DATABASE_DATABASE = "C:\Users\YourName\vmdb.db"

    imo-vmdb initdb
    imo-vmdb import_csv observations-2024.csv
    imo-vmdb normalize
    imo-vmdb web_server

Windows Command Prompt (``cmd.exe``)::

    set IMO_VMDB_DATABASE_DATABASE=C:\Users\YourName\vmdb.db

    imo-vmdb initdb
    imo-vmdb import_csv observations-2024.csv
    imo-vmdb normalize
    imo-vmdb web_server

For the full list of supported variables see
`All Environment Variables`_ above.

**PostgreSQL and MySQL**

For PostgreSQL or MySQL (see `Database`_ above), install the required driver.

In a virtual environment::

    pip install "imo-vmdb[pgsql]"   # PostgreSQL
    pip install "imo-vmdb[mysql]"   # MySQL

With pipx::

    pipx install "imo-vmdb[pgsql]"   # PostgreSQL
    pipx install "imo-vmdb[mysql]"   # MySQL

PostgreSQL and MySQL need more parameters than fit comfortably on a
command line.  Use a configuration file (see below) and pass it with
``-c config.ini``.

Configuration file
******************

A configuration file is the recommended way to manage **PostgreSQL** or
**MySQL** connections, multi-section logging, or any setup more complex
than a single SQLite path.  *imo-vmdb* reads database and logging
settings from an INI file passed with ``-c config.ini``::

    imo-vmdb initdb -c config.ini

Settings from the file take precedence over environment variables, and
both can be combined.

Minimal SQLite configuration (alternative to the environment variable
shown above)::

    [database]
    database = /path/to/database/file.db

On Windows::

    [database]
    database = C:\Users\YourName\vmdb\database.db

Minimal PostgreSQL configuration::

    [database]
    module = psycopg2
    database = vmdb
    user = vmdb

Minimal MySQL configuration::

    [database]
    module = pymysql
    database = vmdb
    user = vmdb
    sql_mode = ANSI
    init_command = SET innodb_lock_wait_timeout=3600

Logging
*******

By default, status messages are printed to the screen.  To write to a file
instead::

    [logging]
    level = INFO
    file = /path/to/logfile.log

``level`` controls verbosity (least to most): ``CRITICAL``, ``ERROR``,
``WARNING``, ``INFO``.

Upgrading from earlier versions
-------------------------------

Some releases introduce incompatible database-schema changes — most recently
**2.0.0** (``rate_magnitude`` table merged into the ``rate`` table) and
**1.8.0** (``city`` → ``location_name``, ``lim_mag`` → ``lim_magn``).
No automatic data migration is performed in either case.

To upgrade, run::

    imo-vmdb initdb         # drops all tables and recreates the new schema
    imo-vmdb import_csv …   # re-import your CSV sources
    imo-vmdb normalize      # rebuild the normalized tables

Review the :doc:`changelog <about>` (or ``CHANGELOG.md`` in the source
distribution) before upgrading, especially the entries flagged
``BREAKING``.
