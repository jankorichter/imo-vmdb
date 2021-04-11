Installation and Setup
======================

Installation
************

*imo-vmdb* requires the `Python interpreter <https://www.python.org/>`_ (version ``>= 3.7``) for execution.
Once installed, simply execute::

 pip install imo-vmdb

to install *imo-vmdb*. The command

.. code-block::

    python -m imo_vmdb

can be used to check whether the installation was successful.
In this case, a simple help text is displayed.

Database
********

*imo-vmdb* uses a configuration file in `INI-format <https://en.wikipedia.org/wiki/INI_file>`_.
`SQLite <https://www.sqlite.org/>`_ is used for a simple database.
The configuration for this is simple.
Only the path to the database file (e.g. ``config.ini``) must be provided.
The configuration file then looks like this, for example::

   [database]
   database = /path/to/database/file.db

For first time use, the database must first be initialized::

    python -m imo_vmdb initdb -c config.ini

.. WARNING::
   If the database already exists, all data will be lost.
   These must then be re-imported.

For more complex installations, `PostgreSQL <https://www.postgresql.org/>`_
as well as `MySQL <https://dev.mysql.com/>`_ (version ``>=8.0``) can be used.
For example, a minimal configuration for *PostgreSQL* is::

    [database]
    module = psycopg2
    database = vmdb
    user = vmdb

The configuration is given by the database adapter `psycopg2 <https://pypi.org/project/psycopg2/>`_.
The options are passed directly to the constructor of the adapter.
Alternatively *MySQL* can be used.
A corresponding configuration with `pymysql <https://pypi.org/project/PyMySQL/>`_ is::

    [database]
    module = pymysql
    database = vmdb
    user = vmdb
    sql_mode = ANSI
    init_command = SET innodb_lock_wait_timeout=3600

Logging
*******

During the import and normalization of the data, *imo-vmdb* outputs information.
This information includes, for example, errors found or hints.
By default, these are output directly.
In the configuration file it is possible to specify which information is output.
Additionally, it can be configured to redirect this information to a file.
For example, such a configuration could look like this::

    [logging]
    level = INFO
    file = /path/to/log/file.log

``file`` specifies the path to which file the information should be written.
``level`` controls the amount of information output, where the following values can be specified:

* ``CRITICAL``
* ``ERROR``
* ``WARNING``
* ``INFO``
