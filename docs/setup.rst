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
        -e IMO_VMDB_WEBUI_UPLOAD_DIR=/data/uploads \
        ghcr.io/jankorichter/imo-vmdb

Replace ``/your/local/data`` with your data folder path.
Open ``http://localhost:8000`` in your browser.  Press ``Ctrl+C`` to stop.

.. note::

   When the container starts, Flask prints the following message:

   .. code-block:: text

      WARNING: This is a development server. Do not use it in a production
      deployment. Use a production WSGI server instead.

   This is expected behaviour.  The warning refers to deployments on a
   public server; it does not apply to local use on your own computer.
   You can safely ignore it.

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
   * - ``IMO_VMDB_WEBUI_UPLOAD_DIR``
     - ``[webui] upload_dir``
     - system temp dir
   * - ``IMO_VMDB_WEBUI_PORT``
     - ``[webui] port``
     - ``8000``

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

If you already have Python 3.10 or newer installed, you can install
*imo-vmdb* directly (system-wide or in a virtual environment).

**System-wide installation**

::

    pip install imo-vmdb

**Virtual environment (recommended for local use)**

A virtual environment keeps *imo-vmdb* isolated from other Python packages
on your system::

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install imo-vmdb

Activate the environment with ``source .venv/bin/activate`` each time you
open a new terminal before running *imo-vmdb*.

Verify the installation::

    python -m imo_vmdb

A short help text listing the available commands should appear.

.. note::
   The rest of this documentation assumes *imo-vmdb* is either installed
   system-wide or that the virtual environment is already activated.

For work with the source code or running from a local clone, see the
``README.md`` in the project root for setup instructions using Poetry.

**PostgreSQL and MySQL**

For PostgreSQL or MySQL (see `Database`_ above), install the required driver::

    pip install "imo-vmdb[pgsql]"   # PostgreSQL
    pip install "imo-vmdb[mysql]"   # MySQL

Configuration file
******************

*imo-vmdb* reads database and logging settings from an INI file passed with
``-c config.ini``.

Minimal SQLite configuration::

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
