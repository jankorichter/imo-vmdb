from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class RadiantParser(CsvParser):
    """CSV parser for radiant drift data (columns: shower, ra, dec, month, day).

    Upserts rows into the ``radiant`` table.  With ``do_delete=True``, all
    existing radiant rows are removed before import.
    """

    _required_columns = (
        ("shower",),
        ("ra",),
        ("dec",),
        ("day",),
        ("month",),
    )

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._delete_stmt = self._db_conn._convert_stmt(
            'DELETE FROM radiant WHERE shower = %(shower)s AND "month" = %(month)s AND "day" = %(day)s'
        )
        self._insert_stmt = self._db_conn._convert_stmt("""
            INSERT INTO radiant (
                shower,
                ra,
                "dec",
                "month",
                "day"
            ) VALUES (
                %(shower)s,
                %(ra)s,
                %(dec)s,
                %(month)s,
                %(day)s
            )
        """)

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn._convert_stmt("DELETE FROM radiant"))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        """Validate and insert a single radiant row.

        :param row: Raw CSV row as a list of strings.
        :param cur: Open database cursor.
        :return: ``True`` on success, ``False`` if the row was skipped due to
            a validation error.
        :raises DBException: On database error.
        """
        row = dict(zip(self.column_names, row, strict=False))

        try:
            shower = self._parse_shower(row["shower"])
            ra = self._parse_ra(row["ra"], shower)
            dec = self._parse_dec(row["dec"], shower)
            month = self._parse_int(row["month"], "month", shower)
            day = self._parse_int(row["day"], "day", shower)
            self._validate_date(month, day, shower)
            if ra is None or dec is None:
                raise ImportException("ID %s: ra and dec must be set." % shower)

        except ImportException as err:
            self._log_error(str(err))
            return False

        record = {
            "shower": shower,
            "ra": ra,
            "dec": dec,
            "month": month,
            "day": day,
        }

        try:
            cur.execute(
                self._delete_stmt, {"shower": shower, "month": month, "day": day}
            )
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_shower(value):
        """Parse and validate a shower code (must be non-empty).

        :param value: Raw shower code string from the CSV.
        :return: Uppercased shower IAU code.
        :raises ImportException: If the value is empty.
        """
        shower = value.strip()
        if "" == shower:
            raise ImportException("Shower code must not be empty.")

        return shower.upper()

    @staticmethod
    def _parse_int(value, ctx, iau_code):
        """Parse a string as an integer.

        :param value: Raw integer string from the CSV.
        :param ctx: Field label used in error messages (e.g. ``'month'``).
        :param iau_code: Shower IAU code used in error messages.
        :return: Parsed integer value.
        :raises ImportException: If the value cannot be converted to an integer.
        """
        value = value.strip()

        try:
            value = int(value)
        except ValueError:
            raise ImportException(
                "ID %s: %s is an invalid %s." % (iau_code, value, ctx)
            )

        return value
