import logging
from datetime import datetime, timedelta


class ImportException(Exception):
    pass


class CsvParser(object):

    _required_columns = {'MFpm+zb9fU7GUP9A'}

    def __init__(self, db_conn, log_handler, do_delete=False, try_repair=False, is_permissive=False):
        self._db_conn = db_conn
        self._log_handler = log_handler
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

    def _init_logger(self, name):
        logger = logging.getLogger(name)
        logger.disabled = True
        logger.setLevel(logging.INFO)
        if self._log_handler is not None:
            logger.addHandler(self._log_handler)
            logger.disabled = False
        self._logger = logger

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
            raise ImportException("id %s: Observation found without a session id." % obs_id)

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException("id %s: invalid session id. Value is (%s)." % (obs_id, session_id))
        if session_id < 1:
            raise ImportException("id %s: session id must be greater than 0 instead of %s." % (obs_id, session_id))

        return session_id

    @staticmethod
    def _parse_observer_id(value, ctx, rec_id):
        observer_id = value.strip()
        if '' == observer_id:
            return None

        try:
            observer_id = int(observer_id)
        except ValueError:
            raise ImportException("id %s: invalid %s. Value is (%s)." % (rec_id, ctx, observer_id))
        if observer_id < 1:
            raise ImportException("id %s: %s must be greater than 0 instead of %s." % (rec_id, ctx, observer_id))

        return observer_id

    def _parse_dec(self, value, rec_id):
        dec = value.strip()
        if '' == dec:
            return None

        try:
            dec = float(dec)
        except ValueError:
            raise ImportException("id %s: invalid declination value %s." % (rec_id, dec))

        if dec in (990.0, 999.0):
            if self._try_repair:
                self._logger.warning(
                    "id %s: invalid declination value %s. It is assumed that the value has not been set." %
                    (rec_id, dec)
                )
                return None
            else:
                raise ImportException("id %s: invalid declination value %s." % (rec_id, dec))

        if dec < -90 or dec > 90:
            raise ImportException("id %s: declination must be between -90 and 90 instead of %s." % (rec_id, dec))

        return dec

    def _parse_ra(self, value, rec_id):
        ra = value.strip()
        if '' == ra:
            return None

        try:
            ra = float(ra)
        except ValueError:
            raise ImportException("id %s: invalid right ascension value %s." % (rec_id, ra))

        if 999.0 == ra:
            if self._try_repair:
                self._logger.warning(
                    "id %s: invalid right ascension value %s. It is assumed that the value has not been set." %
                    (rec_id, ra)
                )
                return None
            else:
                raise ImportException("id %s: invalid right ascension value %s." % (rec_id, ra))

        if ra < 0 or ra > 360:
            raise ImportException("id %s: right ascension must be between 0 and 360 instead of %s." % (rec_id, ra))

        return ra

    def _check_ra_dec(self, ra, dec, record_id):
        if not ((ra is None) ^ (dec is None)):
            return [ra, dec]

        if self._try_repair:
            self._logger.warning(
                (
                    'id %s: ra and dec must be set or both must be undefined.' +
                    ' It is assumed that both values has not been set.'
                ) % record_id
            )
            return [None, None]

        raise ImportException('%s: ra and dec must be set or both must be undefined.' % record_id)

    @staticmethod
    def _parse_date_time(value, ctx, obs_id):
        dt = value.strip()
        if '' == dt:
            raise ImportException("id %s: %s must be set." % (obs_id, ctx))

        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ImportException("id %s: invalid %s value %s." % (obs_id, ctx, dt))

        return dt

    @staticmethod
    def _validate_date(month, day, iau_code, ctx=''):

        if '' != ctx:
            ctx = 'of %s ' % ctx

        if day < 1 or day > 31:
            raise ImportException("id %s: the day %smust be between 1 and 31 instead of %s" % (iau_code, ctx, day))

        if 31 == day and month in [4, 6, 9, 11]:
            raise ImportException("id %s: the day %smust not be 31. The value is %s." % (iau_code, ctx, day))

        if 2 == month and day in [29, 30]:
            raise ImportException("id %s: the day %smust not be 29 or 30. The value is %s." % (iau_code, ctx, day))

        return [month, day]

    def _check_period(self, period_start, period_end, max_period_duration, obs_id):
        logger = self._logger
        if period_start == period_end:
            msg = "id %s: The observation has an incorrect time period. The beginning is equal to the end." % obs_id
            if self._is_permissive:
                logger.warning(msg)
                return period_start, period_end
            else:
                raise ImportException(msg)

        diff = period_end - period_start
        if period_end > period_start and diff > max_period_duration:
            raise ImportException(
                "id %s: The time period of observation is too long (%s - %s)." %
                (obs_id, str(period_start), str(period_end))
            )

        if period_end > period_start:
            return period_start, period_end

        msg = (
            "id %s: The observation has an incorrect time period (%s - %s)." %
            (obs_id, str(period_start), str(period_end))
        )

        if not self._try_repair:
            raise ImportException(msg)

        diff = abs(diff)
        max_diff = timedelta(days=1)
        if diff > max_diff:
            raise ImportException(msg)

        period_end += max_diff
        logger.warning(
            "%s An attempt is made to correct it with (%s - %s)." %
            (msg, str(period_start), str(period_end))
        )

        return self._check_period(period_start, period_end, max_period_duration, obs_id)
