.. _import:

Importing Data
==============

To import the data into the database, the CSV files of the VMDB are imported first.
The import of the data is performed in two stages.
The first stage is called *import*, second stage is called :ref:`normalization <normalization>`.
During import, all records of the CSV files are first checked individually and temporarily stored in the database.

First the import is prepared with the command ``cleanup``::

    python -m imo_vmdb cleanup -c config.ini

Subsequently, several files of the VMDB can be imported.
For example

.. code-block::

    python -m imo_vmdb import_csv -c config.ini data/*-2020.csv

imports all files of the year 2020.
This includes session, rate, and magnitude data of the observations.
If an error occurs with a data record, it will not be imported.
A warning is issued if the data set is recognized as probably incorrect, but is nevertheless accepted.

The following additional options can be passed to the ``import_csv`` command:

*  ``-d`` deletes previously imported data
*  ``-p`` does not apply stringent tests
*  ``-r`` an attempt is made to correct errors

The ``-r`` option tries to repair records.
For example, it tries to detect if the beginning of the observation and the end of the observation have been swapped.
If this is the case, an attempt is made to correct this error.
The ``-r`` option also removes erroneous information in the records, which are considered as optional.
The ``-p`` option ignores non-critical data errors.
Instead of an error, only a warning is issued and the record is imported.
The ``-d`` option replaces already imported records.
This makes it possible to repeat the import without having to call the ``cleanup`` command again.
This can be useful if you only want to overwrite a single record that has already been imported.

After the import, the data can be finally transferred into the database.
This process is called :ref:`normalization <normalization>`.
After normalization is complete, the imported records can be removed from the database with ``cleanup``.
