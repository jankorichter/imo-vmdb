from datetime import datetime, timedelta


class ImportException(Exception):
    """Raised when a CSV row fails validation and cannot be imported."""


class CsvParser:
    """Base class for IMO VMDB CSV format parsers.

    Subclasses declare :attr:`_required_columns` and implement
    :meth:`parse_row`.  Shared field-level validation helpers are provided for
    the types that appear across all IMO VMDB CSV formats.

    :param db_conn: Open :class:`~imo_vmdb.db.DBAdapter` connection.
    :param logger: Logger for warnings and errors.
    :param do_delete: Clear all existing rows from the target table before
        importing.
    :param try_repair: Attempt automatic correction of malformed values such
        as swapped start/end timestamps.
    :param is_permissive: Accept non-critical data errors that would otherwise
        raise :class:`ImportException`.
    """

    _required_columns = {"MFpm+zb9fU7GUP9A"}

    def __init__(
        self, db_conn, logger, do_delete=False, try_repair=False, is_permissive=False
    ):
        self._db_conn = db_conn
        self._logger = logger
        self._do_delete = do_delete
        self._is_permissive = is_permissive
        self._try_repair = try_repair
        self.column_names: tuple[str, ...] = ()
        self.has_errors = False

    @classmethod
    def is_responsible(cls, column_names):
        """Return ``True`` if this parser handles the given CSV column set.

        :param column_names: List of lowercased column header strings.
        :return: ``True`` when :attr:`_required_columns` is a subset of *column_names*.
        """
        return cls._required_columns.issubset(set(column_names))

    def on_start(self, cur):
        """Called once before the first row is processed (e.g. to truncate the table).

        :param cur: Open database cursor.
        """
        pass

    def on_shutdown(self, cur):
        """Called once after all rows have been processed.

        :param cur: Open database cursor.
        """
        pass

    def _log_error(self, msg):
        """Log *msg* as an error and set :attr:`has_errors`.

        :param msg: Error message string.
        """
        self._logger.error(msg)
        self.has_errors = True

    def _log_critical(self, msg):
        """Log *msg* as critical and set :attr:`has_errors`.

        :param msg: Critical message string.
        """
        self._logger.critical(msg)
        self.has_errors = True

    @staticmethod
    def _parse_shower(value):
        """Parse and normalise a shower code.

        Returns ``None`` for sporadics (empty string or ``SPO``).

        :param value: Raw shower code string from the CSV.
        :return: Uppercased IAU shower code, or ``None`` for sporadics.
        """
        shower = value.strip()
        if "" == shower:
            return None

        shower = shower.upper()
        if "SPO" == shower:
            return None

        return shower

    @staticmethod
    def _parse_session_id(value, obs_id):
        """Parse and validate a session ID field.

        :param value: Raw session ID string from the CSV.
        :param obs_id: Observation ID used in error messages.
        :return: Session ID as a positive integer.
        :raises ImportException: If the value is empty, non-integer, or less than 1.
        """
        session_id = value.strip()
        if "" == session_id:
            raise ImportException(
                "ID %s: Observation found without a session id." % obs_id
            )

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException(
                "ID %s: invalid session id. Value is (%s)." % (obs_id, session_id)
            )
        if session_id < 1:
            raise ImportException(
                "ID %s: session ID must be greater than 0 instead of %s."
                % (obs_id, session_id)
            )

        return session_id

    @staticmethod
    def _parse_observer_id(value, rec_id, session_id=None):
        """Parse and validate an optional observer ID field.

        :param value: Raw observer ID string from the CSV.
        :param rec_id: Record ID used in error messages.
        :param session_id: Session ID used to prefix error messages when given.
        :return: Observer ID as a positive integer, or ``None`` if the field is empty.
        :raises ImportException: If the value is non-empty but non-integer or less than 1.
        """
        observer_id = value.strip()

        if "" == observer_id:
            return None

        prefix = (
            "session %s: ID %s" % (session_id, rec_id)
            if session_id is not None
            else "ID %s" % rec_id
        )
        try:
            observer_id = int(observer_id)
        except ValueError:
            raise ImportException(
                "%s: invalid observer id. Value is (%s)." % (prefix, observer_id)
            )
        if observer_id < 1:
            raise ImportException(
                "%s: observer ID must be greater than 0 instead of %s."
                % (prefix, observer_id)
            )

        return observer_id

    def _parse_dec(self, value, rec_id, session_id=None):
        """Parse and validate a declination value in degrees.

        Accepts values in [-90, 90].  The sentinel values 990 and 999 are
        treated as missing when :attr:`_try_repair` is enabled.

        :param value: Raw declination string from the CSV.
        :param rec_id: Record ID used in error messages.
        :param session_id: Session ID used to prefix error messages when given.
        :return: Declination in degrees as a float, or ``None`` if the field is empty.
        :raises ImportException: If the value is invalid and cannot be repaired.
        """
        dec = value.strip()
        if "" == dec:
            return None

        prefix = (
            "session %s: ID %s" % (session_id, rec_id)
            if session_id is not None
            else "ID %s" % rec_id
        )
        try:
            dec = float(dec)
        except ValueError:
            raise ImportException("%s: invalid declination value %s." % (prefix, dec))

        if dec in (990.0, 999.0):
            if self._try_repair:
                self._logger.warning(
                    "%s: invalid declination value %s. It is assumed that the value has not been set."
                    % (prefix, dec)
                )
                return None
            else:
                raise ImportException(
                    "%s: invalid declination value %s." % (prefix, dec)
                )

        if dec < -90 or dec > 90:
            raise ImportException(
                "%s: declination must be between -90 and 90 instead of %s."
                % (prefix, dec)
            )

        return dec

    def _parse_ra(self, value, rec_id, session_id=None):
        """Parse and validate a right ascension value in degrees.

        Accepts values in [0, 360].  The sentinel value 999 is treated as
        missing when :attr:`_try_repair` is enabled.

        :param value: Raw right ascension string from the CSV.
        :param rec_id: Record ID used in error messages.
        :param session_id: Session ID used to prefix error messages when given.
        :return: Right ascension in degrees as a float, or ``None`` if empty.
        :raises ImportException: If the value is invalid and cannot be repaired.
        """
        ra = value.strip()
        if "" == ra:
            return None

        prefix = (
            "session %s: ID %s" % (session_id, rec_id)
            if session_id is not None
            else "ID %s" % rec_id
        )
        try:
            ra = float(ra)
        except ValueError:
            raise ImportException(
                "%s: invalid right ascension value %s." % (prefix, ra)
            )

        if 999.0 == ra:
            if self._try_repair:
                self._logger.warning(
                    "%s: invalid right ascension value %s. It is assumed that the value has not been set."
                    % (prefix, ra)
                )
                return None
            else:
                raise ImportException(
                    "%s: invalid right ascension value %s." % (prefix, ra)
                )

        if ra < 0 or ra > 360:
            raise ImportException(
                "%s: right ascension must be between 0 and 360 instead of %s."
                % (prefix, ra)
            )

        return ra

    def _check_ra_dec(self, ra, dec, rec_id, session_id=None):
        """Ensure that RA and Dec are either both set or both absent.

        :param ra: Parsed right ascension value or ``None``.
        :param dec: Parsed declination value or ``None``.
        :param rec_id: Record ID used in error messages.
        :param session_id: Session ID used to prefix error messages when given.
        :return: List ``[ra, dec]`` — both ``None`` if repair cleared an asymmetric pair.
        :raises ImportException: If only one is set and :attr:`_try_repair` is
            disabled.
        """
        if not ((ra is None) ^ (dec is None)):
            return [ra, dec]

        prefix = (
            "session %s: ID %s" % (session_id, rec_id)
            if session_id is not None
            else "ID %s" % rec_id
        )
        if self._try_repair:
            self._logger.warning(
                "%s: ra and dec must be set or both must be undefined."
                " It is assumed that both values has not been set." % prefix
            )
            return [None, None]

        raise ImportException(
            "%s: ra and dec must be set or both must be undefined." % prefix
        )

    @staticmethod
    def _parse_date_time(value, ctx, obs_id, session_id):
        """Parse a ``YYYY-MM-DD HH:MM:SS`` timestamp string.

        :param value: Raw timestamp string from the CSV.
        :param ctx: Field label used in error messages (e.g. ``'start date'``).
        :param obs_id: Observation ID used in error messages.
        :param session_id: Session ID used in error messages.
        :return: Parsed :class:`~datetime.datetime` object.
        :raises ImportException: If the value is empty or does not match the
            expected format.
        """
        dt = value.strip()
        prefix = "session %s: ID %s" % (session_id, obs_id)
        if "" == dt:
            raise ImportException("%s: %s must be set." % (prefix, ctx))

        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise ImportException("%s: invalid %s value %s." % (prefix, ctx, dt))

        return dt

    @staticmethod
    def _validate_date(month, day, iau_code, ctx=""):
        """Validate that a (month, day) pair represents a plausible calendar date.

        :param month: Month as an integer (1–12).
        :param day: Day as an integer.
        :param iau_code: Shower IAU code used in error messages.
        :param ctx: Optional field label used in error messages.
        :return: List ``[month, day]`` if the date is valid.
        :raises ImportException: If the day is out of range for the given month.
        """
        if "" != ctx:
            ctx = "of %s " % ctx

        if day < 1 or day > 31:
            raise ImportException(
                "ID %s: the day %smust be between 1 and 31 instead of %s"
                % (iau_code, ctx, day)
            )

        if 31 == day and month in [4, 6, 9, 11]:
            raise ImportException(
                "ID %s: the day %smust not be 31. The value is %s."
                % (iau_code, ctx, day)
            )

        if 2 == month and day in [29, 30]:
            raise ImportException(
                "ID %s: the day %smust not be 29 or 30. The value is %s."
                % (iau_code, ctx, day)
            )

        return [month, day]

    def _check_period(
        self, period_start, period_end, max_period_duration, obs_id, session_id
    ):
        """Validate and optionally repair an observation time period.

        Accepts the period unchanged if it is valid.  With :attr:`_try_repair`
        enabled, attempts to fix an inverted or off-by-one-day period by
        choosing the shortest valid candidate (swap, advance end, or move back
        start).

        :param period_start: Observation start :class:`~datetime.datetime`.
        :param period_end: Observation end :class:`~datetime.datetime`.
        :param max_period_duration: Maximum allowed duration as a
            :class:`~datetime.timedelta`.
        :param obs_id: Observation ID used in error messages.
        :param session_id: Session ID used in error messages.
        :return: Tuple ``(period_start, period_end)`` — possibly repaired.
        :raises ImportException: If the period is invalid and cannot be
            repaired, or if no repair candidate is within *max_period_duration*.
        """
        logger = self._logger

        prefix = "session %s: ID %s" % (session_id, obs_id)

        if period_start == period_end:
            msg = (
                "%s: The observation has an incorrect time period. The beginning is equal to the end."
                % prefix
            )
            if self._is_permissive:
                logger.warning(msg)
                return period_start, period_end
            raise ImportException(msg)

        diff = period_end - period_start
        if period_end > period_start:
            if diff > max_period_duration:
                raise ImportException(
                    "%s: The time period of observation is too long (%s - %s)."
                    % (prefix, str(period_start), str(period_end))
                )
            return period_start, period_end

        msg = "%s: The observation has an incorrect time period (%s - %s)." % (
            prefix,
            period_start,
            period_end,
        )

        if not self._try_repair:
            raise ImportException(msg)

        one_day = timedelta(days=1)
        candidates = [
            ("start/end swapped", period_end, period_start),
            ("end date advanced by 1 day", period_start, period_end + one_day),
            ("start date moved back by 1 day", period_start - one_day, period_end),
        ]

        valid = []
        for preference, (label, s, e) in enumerate(candidates):
            duration = e - s
            if s < e and duration <= max_period_duration:
                valid.append((duration, preference, label, s, e))

        if not valid:
            raise ImportException(msg)

        # Pick shortest duration; use list order as tiebreaker.
        _, _, best_label, best_start, best_end = min(valid)

        logger.warning(
            "%s: Time period corrected (%s): %s - %s -> %s - %s"
            % (prefix, best_label, period_start, period_end, best_start, best_end)
        )
        return best_start, best_end
