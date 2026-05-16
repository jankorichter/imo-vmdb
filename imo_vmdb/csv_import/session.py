from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class SessionParser(CsvParser):
    """CSV parser for observer session data.

    Upserts rows into the ``imported_session`` table (delete by session ID,
    then insert).  With ``do_delete=True``, all existing rows are removed
    before import.
    """

    _required_columns = {
        "session id",
        "observer id",
        "actual observer name",
        "latitude",
        "longitude",
        "elevation",
        "city",
        "country",
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._delete_stmt = self._db_conn._convert_stmt(
            "DELETE FROM imported_session WHERE id = %(id)s"
        )
        self._insert_stmt = self._db_conn._convert_stmt("""
            INSERT INTO imported_session (
                id,
                observer_id,
                observer_name,
                latitude,
                longitude,
                elevation,
                location_name,
                country
            ) VALUES (
                %(id)s,
                %(observer_id)s,
                %(observer_name)s,
                %(latitude)s,
                %(longitude)s,
                %(elevation)s,
                %(location_name)s,
                %(country)s
            )
        """)

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn._convert_stmt("DELETE FROM imported_session"))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        """Validate and insert a single session row.

        :param row: Raw CSV row as a list of strings.
        :param cur: Open database cursor.
        :return: ``True`` on success, ``False`` if the row was skipped due to
            a validation error.
        :raises DBException: On database error.
        """
        row = dict(zip(self.column_names, row, strict=False))

        try:
            session_id = self._parse_session_id(row["session id"])
            lat = self._parse_latitude(row["latitude"], session_id)
            long = self._parse_longitude(row["longitude"], session_id)
            elevation = self._parse_elevation(row["elevation"], session_id)
            observer_id = self._parse_observer_id(row["observer id"], session_id)
            observer_name = self._parse_observer_name(
                row["actual observer name"], session_id
            )
            location_name = self._parse_text(row["city"], "city", session_id)
            country = self._parse_text(row["country"], "country", session_id)
        except ImportException as err:
            self._log_error(str(err))
            return False

        record = {
            "id": session_id,
            "observer_id": observer_id,
            "observer_name": observer_name,
            "latitude": lat,
            "longitude": long,
            "elevation": elevation,
            "location_name": location_name,
            "country": country,
        }

        try:
            cur.execute(self._delete_stmt, {"id": session_id})
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_session_id(value, obs_id=None):
        """Parse and validate a session ID field.

        :param value: Raw session ID string from the CSV.
        :param obs_id: Unused; kept for signature compatibility with the base class.
        :return: Session ID as a positive integer.
        :raises ImportException: If the value is empty, non-integer, or less than 1.
        """
        session_id = value.strip()
        if "" == session_id:
            raise ImportException("Session found without a session id.")

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException("ID %s: invalid session id." % session_id)
        if session_id < 1:
            raise ImportException(
                "ID %s: session ID must be greater than 0." % session_id
            )

        return session_id

    @staticmethod
    def _parse_latitude(value, session_id):
        """Parse and validate a geographic latitude value in degrees.

        :param value: Raw latitude string from the CSV.
        :param session_id: Session ID used in error messages.
        :return: Latitude in degrees as a float in [-90, 90].
        :raises ImportException: If the value is empty, non-numeric, or out of range.
        """
        lat = value.strip()
        if "" == lat:
            raise ImportException("ID %s: latitude must not be empty." % session_id)

        try:
            lat = float(lat)
        except ValueError:
            raise ImportException(
                "ID %s: invalid latitude value. The value is %s." % (session_id, lat)
            )

        if lat < -90 or lat > 90:
            raise ImportException(
                "ID %s: latitude must be between -90 and 90 instead of %s."
                % (session_id, lat)
            )

        return lat

    @staticmethod
    def _parse_longitude(value, session_id):
        """Parse and validate a geographic longitude value in degrees.

        :param value: Raw longitude string from the CSV.
        :param session_id: Session ID used in error messages.
        :return: Longitude in degrees as a float in [-180, 180].
        :raises ImportException: If the value is empty, non-numeric, or out of range.
        """
        long = value.strip()
        if "" == long:
            raise ImportException("ID %s: longitude must not be empty." % session_id)

        try:
            long = float(long)
        except ValueError:
            raise ImportException(
                "ID %s: invalid longitude value. The value is %s." % (session_id, long)
            )

        if long < -180 or long > 180:
            raise ImportException(
                "ID %s: longitude must be between -180 and 180 instead of %s."
                % (session_id, long)
            )

        return long

    def _parse_elevation(self, value, session_id):
        """Parse and validate a site elevation value in metres.

        :param value: Raw elevation string from the CSV.
        :param session_id: Session ID used in error messages.
        :return: Elevation as a float, or ``None`` if empty and
            :attr:`_is_permissive` is enabled.
        :raises ImportException: If the value is empty (in strict mode) or
            non-numeric.
        """
        elevation = value.strip()
        if "" == elevation:
            if self._is_permissive:
                return None
            else:
                raise ImportException(
                    "ID %s: elevation must not be empty." % session_id
                )

        try:
            elevation = float(elevation)
        except ValueError:
            raise ImportException(
                "ID %s: invalid elevation value. The value is %s."
                % (session_id, elevation)
            )

        return elevation

    @staticmethod
    def _parse_text(value, ctx, session_id):
        """Parse and validate a required text field.

        :param value: Raw string from the CSV.
        :param ctx: Field label used in error messages (e.g. ``'city'``).
        :param session_id: Session ID used in error messages.
        :return: Stripped non-empty string.
        :raises ImportException: If the value is empty or cannot be converted
            to a string.
        """
        value = value.strip()
        if "" == value:
            raise ImportException("ID %s: %s must be set." % (session_id, ctx))

        try:
            value = str(value)
        except ValueError:
            raise ImportException(
                "ID %s: invalid %s. Value is %s." % (session_id, ctx, value)
            )

        return value

    def _parse_observer_name(self, value, session_id):
        """Parse an optional observer name field.

        :param value: Raw observer name string from the CSV.
        :param session_id: Session ID used in error and warning messages.
        :return: Stripped observer name string, or ``None`` if empty.
        """
        value = value.strip()
        if "" == value:
            self._logger.warning("ID %s: observer name is empty." % session_id)
            return None

        return self._parse_text(value, "observer name", session_id)
