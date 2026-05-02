from datetime import datetime, timedelta


class ImportException(Exception):
    pass


class CsvParser(object):

    _required_columns = {'MFpm+zb9fU7GUP9A'}

    def __init__(self, db_conn, logger, do_delete=False, try_repair=False, is_permissive=False):
        self._db_conn = db_conn
        self._logger = logger
        self._do_delete = do_delete
        self._is_permissive = is_permissive
        self._try_repair = try_repair
        self.column_names = ()
        self.has_errors = False

    @classmethod
    def is_responsible(cls, column_names):
        return cls._required_columns.issubset(set(column_names))

    def on_start(self, cur):
        pass

    def on_shutdown(self, cur):
        pass

    def _log_error(self, msg):
        self._logger.error(msg)
        self.has_errors = True

    def _log_critical(self, msg):
        self._logger.critical(msg)
        self.has_errors = True

    @staticmethod
    def _parse_shower(value):
        shower = value.strip()
        if '' == shower:
            return None

        shower = shower.upper()
        if 'SPO' == shower:
            return None

        return shower

    @staticmethod
    def _parse_session_id(value, obs_id):
        session_id = value.strip()
        if '' == session_id:
            raise ImportException('ID %s: Observation found without a session id.' % obs_id)

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException('ID %s: invalid session id. Value is (%s).' % (obs_id, session_id))
        if session_id < 1:
            raise ImportException('ID %s: session ID must be greater than 0 instead of %s.' % (obs_id, session_id))

        return session_id

    @staticmethod
    def _parse_observer_id(value, rec_id, session_id=None):
        observer_id = value.strip()

        if '' == observer_id:
            return None

        prefix = 'session %s: ID %s' % (session_id, rec_id) if session_id is not None else 'ID %s' % rec_id
        try:
            observer_id = int(observer_id)
        except ValueError:
            raise ImportException('%s: invalid observer id. Value is (%s).' % (prefix, observer_id))
        if observer_id < 1:
            raise ImportException('%s: observer ID must be greater than 0 instead of %s.' % (prefix, observer_id))

        return observer_id

    def _parse_dec(self, value, rec_id, session_id=None):
        dec = value.strip()
        if '' == dec:
            return None

        prefix = 'session %s: ID %s' % (session_id, rec_id) if session_id is not None else 'ID %s' % rec_id
        try:
            dec = float(dec)
        except ValueError:
            raise ImportException('%s: invalid declination value %s.' % (prefix, dec))

        if dec in (990.0, 999.0):
            if self._try_repair:
                self._logger.warning(
                    '%s: invalid declination value %s. It is assumed that the value has not been set.' %
                    (prefix, dec)
                )
                return None
            else:
                raise ImportException('%s: invalid declination value %s.' % (prefix, dec))

        if dec < -90 or dec > 90:
            raise ImportException('%s: declination must be between -90 and 90 instead of %s.' % (prefix, dec))

        return dec

    def _parse_ra(self, value, rec_id, session_id=None):
        ra = value.strip()
        if '' == ra:
            return None

        prefix = 'session %s: ID %s' % (session_id, rec_id) if session_id is not None else 'ID %s' % rec_id
        try:
            ra = float(ra)
        except ValueError:
            raise ImportException('%s: invalid right ascension value %s.' % (prefix, ra))

        if 999.0 == ra:
            if self._try_repair:
                self._logger.warning(
                    '%s: invalid right ascension value %s. It is assumed that the value has not been set.' %
                    (prefix, ra)
                )
                return None
            else:
                raise ImportException('%s: invalid right ascension value %s.' % (prefix, ra))

        if ra < 0 or ra > 360:
            raise ImportException('%s: right ascension must be between 0 and 360 instead of %s.' % (prefix, ra))

        return ra

    def _check_ra_dec(self, ra, dec, rec_id, session_id=None):
        if not ((ra is None) ^ (dec is None)):
            return [ra, dec]

        prefix = 'session %s: ID %s' % (session_id, rec_id) if session_id is not None else 'ID %s' % rec_id
        if self._try_repair:
            self._logger.warning(
                '%s: ra and dec must be set or both must be undefined.'
                ' It is assumed that both values has not been set.' % prefix
            )
            return [None, None]

        raise ImportException('%s: ra and dec must be set or both must be undefined.' % prefix)

    @staticmethod
    def _parse_date_time(value, ctx, obs_id, session_id):
        dt = value.strip()
        prefix = 'session %s: ID %s' % (session_id, obs_id)
        if '' == dt:
            raise ImportException('%s: %s must be set.' % (prefix, ctx))

        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ImportException('%s: invalid %s value %s.' % (prefix, ctx, dt))

        return dt

    @staticmethod
    def _validate_date(month, day, iau_code, ctx=''):

        if '' != ctx:
            ctx = 'of %s ' % ctx

        if day < 1 or day > 31:
            raise ImportException(
                'ID %s: the day %smust be between 1 and 31 instead of %s' %
                (iau_code, ctx, day)
            )

        if 31 == day and month in [4, 6, 9, 11]:
            raise ImportException(
                'ID %s: the day %smust not be 31. The value is %s.' %
                (iau_code, ctx, day)
            )

        if 2 == month and day in [29, 30]:
            raise ImportException('ID %s: the day %smust not be 29 or 30. The value is %s.' % (iau_code, ctx, day))

        return [month, day]

    def _check_period(self, period_start, period_end, max_period_duration, obs_id, session_id):
        logger = self._logger

        prefix = 'session %s: ID %s' % (session_id, obs_id)

        if period_start == period_end:
            msg = '%s: The observation has an incorrect time period. The beginning is equal to the end.' % prefix
            if self._is_permissive:
                logger.warning(msg)
                return period_start, period_end
            raise ImportException(msg)

        diff = period_end - period_start
        if period_end > period_start:
            if diff > max_period_duration:
                raise ImportException(
                    '%s: The time period of observation is too long (%s - %s).' %
                    (prefix, str(period_start), str(period_end))
                )
            return period_start, period_end

        msg = '%s: The observation has an incorrect time period (%s - %s).' % (prefix, period_start, period_end)

        if not self._try_repair:
            raise ImportException(msg)

        one_day = timedelta(days=1)
        candidates = [
            ('start/end swapped',              period_end,             period_start),
            ('end date advanced by 1 day',     period_start,           period_end + one_day),
            ('start date moved back by 1 day', period_start - one_day, period_end),
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
            '%s: Time period corrected (%s): %s - %s -> %s - %s' %
            (prefix, best_label, period_start, period_end, best_start, best_end)
        )
        return best_start, best_end
