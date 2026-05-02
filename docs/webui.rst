.. _webui:

Web UI
======

The web UI is a browser-based control panel for *imo-vmdb*.  It lets you
initialise the database, import and process observation data, and download
results as CSV files — all from a browser, without using a terminal.

Open ``http://localhost:8000`` in your browser to access the control panel.
For instructions on how to start the server, see :ref:`cli` (Python) or
:ref:`setup` (Docker).

.. note::

   When the server starts, Flask prints the following message:

   .. code-block:: text

      WARNING: This is a development server. Do not use it in a production
      deployment. Use a production WSGI server instead.

   This is expected behaviour.  The warning refers to deployments on a
   public server; it does not apply to local use on your own computer.
   You can safely ignore it.

Control panel
-------------

The control panel consists of four action cards.

**Init Database**
    Creates the database schema from scratch.  Run this once before the first
    import.

    .. warning::
       All existing data in the database will be permanently deleted.
       A confirmation dialog is shown before the operation starts.

**Import CSV**
    Upload one or more CSV files from your computer.  The files are validated
    record by record; invalid records are rejected and a report is written to
    the log.

    Three options are available:

    * *Delete existing imported data* — removes all previously imported raw
      data before the new import begins.  Useful when re-importing a file you
      have already imported, without having to run Cleanup first.
      (CLI equivalent: ``-d``)
    * *Permissive mode* — accepts records with minor data problems that would
      otherwise be rejected, issuing a warning instead of an error.
      (CLI equivalent: ``-p``)
    * *Attempt repair on errors* — tries to automatically correct common
      problems such as swapped start/end times or invalid optional fields.
      (CLI equivalent: ``-r``)

    For the expected file format and column names, see :ref:`csv-import`.

**Normalize**
    Processes all imported records and enriches each observation with computed
    astronomical data: solar longitude, radiant position, sun and moon position
    and illumination.  Run this after every import.

**Cleanup**
    Removes the raw imported data from the database.  The normalized results
    are preserved.  Run this after normalization is complete to free up space.

Downloads
---------

A Downloads section below the action cards provides direct links to export
all tables as CSV files.

Enabling *Export for re-import* changes the Showers and Radiants download
links to export the original reference file format.  These files can be
edited and re-imported with *Import CSV*.  Without this option, all tables
are exported in the database column format (see :ref:`fields`).

Log output
----------

All operations stream their log output live to the log area at the bottom of
the page.  While a job is running, all action buttons are disabled to prevent
concurrent database access.

Three buttons are available above the log area:

* **Copy** — copies the entire log to the clipboard
* **Download** — saves the log as a ``.log`` file with a timestamp
* **Clear** — clears the log area
