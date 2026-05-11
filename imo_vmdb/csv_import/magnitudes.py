import json
import math
from datetime import timedelta

from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class MagnitudesParser(CsvParser):
    """CSV parser for magnitude distribution data.

    Reads per-magnitude counts (mag n6 … mag 7) and stores them as a JSON
    blob in ``imported_magnitude``.  Rows with a total meteor count of zero
    are silently skipped.  With ``do_delete=True``, all existing rows are
    removed before import.
    """

    _required_columns = {
        "magnitude id",
        "user id",
        "obs session id",
        "shower",
        "start date",
        "end date",
        "mag n6",
        "mag n5",
        "mag n4",
        "mag n3",
        "mag n2",
        "mag n1",
        "mag 0",
        "mag 1",
        "mag 2",
        "mag 3",
        "mag 4",
        "mag 5",
        "mag 6",
        "mag 7",
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._delete_stmt = self._db_conn._convert_stmt(
            "DELETE FROM imported_magnitude WHERE id = %(id)s"
        )
        self._insert_stmt = self._db_conn._convert_stmt("""
            INSERT INTO imported_magnitude (
                id,
                observer_id,
                session_id,
                shower,
                "start",
                "end",
                magn
            ) VALUES (
                %(id)s,
                %(observer_id)s,
                %(session_id)s,
                %(shower)s,
                %(start)s,
                %(end)s,
                %(magn)s
            )
        """)

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(
                    self._db_conn._convert_stmt("DELETE FROM imported_magnitude")
                )
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        """Validate and insert a single magnitude observation row.

        :param row: Raw CSV row as a list of strings.
        :param cur: Open database cursor.
        :return: ``True`` on success, ``False`` if the row was skipped due to
            a validation error.
        :raises DBException: On database error.
        """
        row = dict(zip(self.column_names, row, strict=False))

        try:
            magn_id = self._parse_magn_id(row["magnitude id"])
            session_id = self._parse_session_id(row["obs session id"], magn_id)
            observer_id = self._parse_observer_id(
                row["user id"], row["user id"], session_id
            )
            shower = self._parse_shower(row["shower"])
            period_start = self._parse_date_time(
                row["start date"], "start date", magn_id, session_id
            )
            period_end = self._parse_date_time(
                row["end date"], "end date", magn_id, session_id
            )
            period_start, period_end = self._check_period(
                period_start, period_end, timedelta(days=0.49), magn_id, session_id
            )
        except ImportException as err:
            self._log_error(str(err))
            return False

        magn = {}
        try:
            for column in range(1, 7):
                n = float(row["mag n" + str(column)])
                magn[str(-column)] = n

            for column in range(0, 8):
                n = float(row["mag " + str(column)])
                magn[str(column)] = n
        except ValueError:
            self._log_error(
                "session %s: ID %s: Invalid count value of magnitudes found."
                % (session_id, magn_id)
            )
            return False

        try:
            for m, n in magn.items():
                self._validate_count(n, m, magn_id, session_id)
            self._validate_total_count(magn, magn_id, session_id)
        except ImportException as err:
            self._log_error(str(err))
            return False

        freq = int(sum(n for n in magn.values()))
        if 0 == freq:
            return True

        magn = json.dumps({m: n for m, n in magn.items() if n > 0})

        record = {
            "id": magn_id,
            "observer_id": observer_id,
            "session_id": session_id,
            "shower": shower,
            "start": period_start.isoformat(sep=" "),
            "end": period_end.isoformat(sep=" "),
            "magn": magn,
        }

        try:
            cur.execute(self._delete_stmt, {"id": magn_id})
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_magn_id(value):
        """Parse and validate a magnitude observation ID field.

        :param value: Raw magnitude ID string from the CSV.
        :return: Magnitude ID as a positive integer.
        :raises ImportException: If the value is empty, non-integer, or less than 1.
        """
        magn_id = value.strip()
        if "" == magn_id:
            raise ImportException("Observation found without a magnitude id.")

        try:
            magn_id = int(magn_id)
        except ValueError:
            raise ImportException("ID %s: invalid magnitude id." % magn_id)
        if magn_id < 1:
            raise ImportException(
                "ID %s: magnitude ID must be greater than 0." % magn_id
            )

        return magn_id

    @staticmethod
    def _validate_count(n, m, magn_id, session_id):
        """Validate that a per-magnitude count is non-negative and a whole or half number.

        :param n: Count value to validate.
        :param m: Magnitude class (string key) used in error messages.
        :param magn_id: Magnitude ID used in error messages.
        :param session_id: Session ID used in error messages.
        :raises ImportException: If *n* is negative or not a whole or half-integer.
        """
        if n < 0.0:
            raise ImportException(
                "session %s: ID %s: Invalid count %s found for a meteor magnitude of %s."
                % (session_id, magn_id, n, m)
            )

        n_cmp = math.floor(n)
        if n == n_cmp:
            return

        n_cmp += 0.5
        if n == n_cmp:
            return

        raise ImportException(
            "session %s: ID %s: Invalid count %s found for a meteor magnitude of %s."
            % (session_id, magn_id, n, m)
        )

    def _validate_total_count(self, magn, magn_id, session_id):
        """Validate that the sum of all magnitude counts is a whole number.

        :param magn: Dict mapping magnitude class strings to count values.
        :param magn_id: Magnitude ID used in error messages.
        :param session_id: Session ID used in error messages.
        :raises ImportException: If the cumulative sum contains a fractional
            remainder or the total is not an integer.
        """
        is_permissive = self._is_permissive
        n_sum = 0
        for m in sorted(magn.keys(), key=int):
            n = magn[m]
            n_sum += n
            if not is_permissive and 0 == n and math.floor(n_sum) != n_sum:
                raise ImportException(
                    "session %s: ID %s: Inconsistent total count of meteors found."
                    % (session_id, magn_id)
                )

        if math.floor(n_sum) != n_sum:
            raise ImportException(
                "session %s: ID %s: The count of meteors out of a total of %s is invalid."
                % (session_id, magn_id, n_sum)
            )
