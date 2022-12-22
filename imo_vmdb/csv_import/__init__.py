from datetime import datetime, timedelta


class ImportException(Exception):
    pass


class CsvParser(object):

    _required_columns = {'MFpm+zb9fU7GUP9A'}

    def __init__(self, db_conn, logger_factory, do_delete=False, try_repair=False, is_permissive=False):
        self._db_conn = db_conn
        self._logger_factory = logger_factory
        self._logger = None
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
        session_msg = ''
        if session_id is not None:
            session_msg = ' in session %s' % session_id

        if '' == observer_id:
            return None

        try:
            observer_id = int(observer_id)
        except ValueError:
            raise ImportException('ID %s%s: invalid observer id. Value is (%s).' % (rec_id, session_msg, observer_id))
        if observer_id < 1:
            raise ImportException(
                'ID %s%s: observer ID must be greater than 0 instead of %s.' %
                (rec_id, session_msg, observer_id)
            )

        return observer_id

    def _parse_dec(self, value, rec_id, session_id=None):
        dec = value.strip()
        if '' == dec:
            return None

        session_msg = ''
        if session_id is not None:
            session_msg = ' in session %s' % session_id

        try:
            dec = float(dec)
        except ValueError:
            raise ImportException(
                'ID %s%s: invalid declination value %s.' %
                (rec_id, session_msg, dec)
            )

        if dec in (990.0, 999.0):
            if self._try_repair:
                self._logger.warning(
                    'ID %s%s: invalid declination value %s. It is assumed that the value has not been set.' %
                    (rec_id, session_msg, dec)
                )
                return None
            else:
                raise ImportException(
                    'ID %s%s: invalid declination value %s.' %
                    (rec_id, session_msg, dec)
                )

        if dec < -90 or dec > 90:
            raise ImportException(
                'ID %s%s: declination must be between -90 and 90 instead of %s.' %
                (rec_id, session_msg, dec)
            )

        return dec

    def _parse_ra(self, value, rec_id, session_id=None):
        ra = value.strip()
        if '' == ra:
            return None

        session_msg = ''
        if session_id is not None:
            session_msg = ' in session %s' % session_id

        try:
            ra = float(ra)
        except ValueError:
            raise ImportException('ID %s%s: invalid right ascension value %s.' % (rec_id, session_msg, ra))

        if 999.0 == ra:
            if self._try_repair:
                self._logger.warning(
                    'ID %s%s: invalid right ascension value %s. It is assumed that the value has not been set.' %
                    (rec_id, session_msg, ra)
                )
                return None
            else:
                raise ImportException(
                    'ID %s%s: invalid right ascension value %s.' %
                    (rec_id, session_msg, ra)
                )

        if ra < 0 or ra > 360:
            raise ImportException(
                'ID %s%s: right ascension must be between 0 and 360 instead of %s.' %
                (rec_id, session_msg, ra)
            )

        return ra

    def _check_ra_dec(self, ra, dec, rec_id, session_id=None):
        if not ((ra is None) ^ (dec is None)):
            return [ra, dec]

        session_msg = ''
        if session_id is not None:
            session_msg = ' in session %s' % session_id

        if self._try_repair:
            self._logger.warning(
                (
                    'ID %s%s: ra and dec must be set or both must be undefined.' +
                    ' It is assumed that both values has not been set.'
                ) % (rec_id, session_msg)
            )
            return [None, None]

        raise ImportException('%s%s: ra and dec must be set or both must be undefined.' % (rec_id, session_msg))

    @staticmethod
    def _parse_date_time(value, ctx, obs_id, session_id):
        dt = value.strip()
        if '' == dt:
            raise ImportException('ID %s in session %s: %s must be set.' % (obs_id, session_id, ctx))

        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ImportException('ID %s in session %s: invalid %s value %s.' % (obs_id, session_id, ctx, dt))

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

    def _check_period(self, period_start, period_end, max_period_duration, obs_id, session_id, try_repair=None):
        logger = self._logger
        if period_start == period_end:
            msg = 'The observation has an incorrect time period. The beginning is equal to the end.'
            msg = 'ID %s in session %s: %s' % (obs_id, session_id, msg)
            if self._is_permissive:
                logger.warning(msg)
                return period_start, period_end
            else:
                raise ImportException(msg)

        diff = period_end - period_start
        if period_end > period_start and diff > max_period_duration:
            raise ImportException(
                'ID %s in session %s: The time period of observation is too long (%s - %s).' %
                (obs_id, session_id, str(period_start), str(period_end))
            )

        if period_end > period_start:
            return period_start, period_end

        msg = (
            'ID %s in session %s: The observation has an incorrect time period (%s - %s).' %
            (obs_id, session_id, str(period_start), str(period_end))
        )

        try_repair = self._try_repair if try_repair is None else try_repair
        if not try_repair:
            raise ImportException(msg)

        logger.warning(
            '%s An attempt is made to correct it with (%s - %s).' %
            (msg, str(period_end), str(period_start))
        )
        try:
            return self._check_period(
                period_end,
                period_start,
                max_period_duration,
                obs_id,
                session_id,
                try_repair=False
            )
        except ImportException:
            pass

        diff = abs(diff)
        max_diff = timedelta(days=1)
        if diff > max_diff:
            raise ImportException(msg)

        period_end += max_diff
        logger.warning(
            '%s An attempt is made to correct it with (%s - %s).' %
            (msg, str(period_start), str(period_end))
        )

        return self._check_period(
            period_start,
            period_end,
            max_period_duration,
            obs_id,
            session_id,
            try_repair=False
        )
