Installation
============

*imo-vmdb* requires the `Python interpreter <https://www.python.org/>`_ (version ``>= 3.7``) for execution.
Once installed, simply execute::

 pip install imo-vmdb

to install *imo-vmdb*. The command

.. code-block::

    python -m imo_vmdb

can be used to check whether the installation was successful.
In this case, a simple help text is displayed.

Configuration for SQLite:

.. code-block::

   [database]
   module = sqlite3
   database = test.db

Configuration for PostgreSQL:

.. code-block::

    [database]
    module = psycopg2
    database = vmdb
    user = vmdb

Configuration for MySQL:

.. code-block::

    [database]
    module = pymysql
    database = vmdb
    user = vmdb
    sql_mode = ANSI
    init_command = SET innodb_lock_wait_timeout=3600

Configuration for logging:

.. code-block::

    [logging]
    level = INFO
    file = test.log
