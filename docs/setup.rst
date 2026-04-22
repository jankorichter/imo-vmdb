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

*imo-vmdb* supports three database systems.  For most users, **SQLite** is
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

----

Docker
------

Docker lets you run *imo-vmdb* without installing Python or any other
programming tools.  It works by running the software in an isolated
*container* — think of it as a self-contained box that has everything
it needs built in.

There are two ways to work with Docker:

* **Docker Desktop** — a graphical application for Windows and macOS.
  No terminal required.  Recommended if you are new to Docker.
* **Command line** — for users already familiar with Docker and the terminal.

Docker Desktop (recommended for beginners)
******************************************

**What is Docker Desktop?**

`Docker Desktop <https://docs.docker.com/get-docker/>`_ is a free application
that lets you manage containers through a graphical interface — no terminal
needed.  It is available for Windows and macOS.

**Step 1 — Install Docker Desktop**

Download and install `Docker Desktop <https://docs.docker.com/get-docker/>`_.
After installation, start it and wait until the status indicator in the menu
bar shows *"Docker Desktop is running"*.

**Step 2 — Create a data folder**

*imo-vmdb* needs a folder on your computer to store the database and uploaded
CSV files.  Create a dedicated folder now, for example:

* Windows: ``C:\Users\YourName\imo-vmdb-data``
* macOS: ``~/imo-vmdb-data``

Remember this path — you will need it in the next step.

**Step 3 — Find and run the image**

1. Open Docker Desktop.
2. Click the **search bar** at the top of the window and type::

       ghcr.io/jankorichter/imo-vmdb

3. Select the image from the search results.  Docker Desktop will pull
   (download) it automatically if it is not yet on your computer.
4. Click **Run**.  A dialog appears — click **Optional settings** to expand
   the configuration area.

Now fill in three sections:

*Ports* — map port 8000 so your browser can reach the web UI:

.. list-table::
   :widths: 40 40
   :header-rows: 1

   * - Host port
     - Container port
   * - ``8000``
     - ``8000``

If port 8000 is already in use on your computer, choose a different host port
(e.g. ``8080``) and open ``http://localhost:8080`` later.

*Volumes* — connect your data folder to the container:

.. list-table::
   :widths: 40 40
   :header-rows: 1

   * - Host path
     - Container path
   * - ``/your/local/data``
     - ``/data``

Replace ``/your/local/data`` with the folder you created in Step 2.
This ensures your data is saved on your computer even after the container
is stopped or removed.

*Environment variables* — tell the container where to store the database
and uploaded files:

.. list-table::
   :widths: 40 40
   :header-rows: 1

   * - Variable
     - Value
   * - ``IMO_VMDB_DATABASE_DATABASE``
     - ``/data/vmdb.db``
   * - ``IMO_VMDB_WEBUI_UPLOAD_DIR``
     - ``/data/uploads``

Both paths point inside the container (``/data``) and are covered by the
volume above, so the files end up in your data folder on the computer.

5. Click **Run**.
6. Open ``http://localhost:8000`` in your browser.

See :ref:`webui` for a description of all available functions.

**Stopping the container**

1. In Docker Desktop, click **Containers** in the left sidebar.
2. Find the running *imo-vmdb* container in the list.
3. Hover over it — action buttons appear on the right.
4. Click the **Stop** button (square icon).

Your data in the local folder is always preserved.

**Updating to a new version**

Search for the image again (Step 3) and pull the latest version.
Then run a new container with the same settings.

----

Command Line (for experienced Docker users)
*******************************************

Starting the web UI::

    docker run --rm \
        -p 8000:8000 \
        -v /your/local/data:/data \
        -e IMO_VMDB_DATABASE_DATABASE=/data/vmdb.db \
        -e IMO_VMDB_WEBUI_UPLOAD_DIR=/data/uploads \
        ghcr.io/jankorichter/imo-vmdb

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
*imo-vmdb* with pip::

    pip install imo-vmdb

Verify the installation::

    python -m imo_vmdb

A short help text listing the available commands should appear.

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

.. warning::
   Running ``initdb`` on an existing database will delete all data in it.

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
