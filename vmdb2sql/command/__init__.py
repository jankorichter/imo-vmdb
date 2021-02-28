from datetime import datetime, timedelta


class ImportException(Exception):
    pass


class CsvImport(object):

    def __init__(self, db_conn, logger):
        self.db_conn = db_conn
        self.logger = logger
        self.counter_read = 0
        self.counter_write = 0
        self.has_errors = False
        self.required_columns = None

    def _get_column_names(self, row):
        column_names = [r.lower() for r in row]

        if not self.required_columns.issubset(set(column_names)):
            fields = ', '.join(self.required_columns)
            self.logger.critical('The CSV file does not provide the fields %s' % fields)
            self.has_errors = True
            return None

        return column_names

    def _parse_csv_files(self, cur, files_list):
        logger = self.logger

        for file_path in files_list:
            logger.info("Start parsing the data from file %s." % file_path)

            try:
                with open(file_path, mode='r', encoding='utf-8-sig') as csv_file:
                    self._parse_csv_file(cur, csv_file)
            except FileNotFoundError:
                self._log_critical("The file %s could not be found." % file_path)
                continue
            except IsADirectoryError:
                self._log_critical("The file %s is a directory." % file_path)
                continue
            except PermissionError:
                self._log_critical("File %s could not be opened." % file_path)
                continue

            logger.info(
                "Parsing of file %s has finished." % file_path
            )

    def _parse_csv_file(self, cur, csv_file):
        pass

    def _commit(self, cur):
        cur.close()
        self.db_conn.commit()
        self.logger.info(
            "Parsing of the files has finished. %s of %s records were imported." %
            (self.counter_write, self.counter_read)
        )

    def _log_error(self, msg):
        self.logger.error(msg)
        self.has_errors = True

    def _log_critical(self, msg):
        self.logger.critical(msg)
        self.has_errors = True

    @staticmethod
    def _parse_shower(rec):
        shower = rec.strip()
        if '' == shower:
            return None

        shower = shower.upper()
        if 'SPO' == shower:
            return None

        return shower

    @staticmethod
    def _parse_session_id(rec, obs_id):
        session_id = rec.strip()
        if '' == session_id:
            raise ImportException("%s: Observation found without a session id." % obs_id)

        try:
            session_id = int(session_id)
        except ValueError:
            raise ImportException("%s: invalid session id. Value is (%s)." % (obs_id, session_id))
        if session_id < 1:
            raise ImportException("%s: session id must be greater than 0 instead of %s." % (obs_id, session_id))

        return session_id

    @staticmethod
    def _parse_observer_id(rec, ctx, rec_id):
        observer_id = rec.strip()
        if '' == observer_id:
            return None

        try:
            observer_id = int(observer_id)
        except ValueError:
            raise ImportException("%s: invalid %s. Value is (%s)." % (rec_id, ctx, observer_id))
        if observer_id < 1:
            raise ImportException("%s: %s must be greater than 0 instead of %s." % (rec_id, ctx, observer_id))

        return observer_id

    def _parse_dec(self, rec, rec_id):
        dec = rec.strip()
        if '' == dec:
            return None

        try:
            dec = float(dec)
        except ValueError:
            raise ImportException("%s: invalid declination value %s." % (rec_id, dec))

        if dec in (990.0, 999.0):
            self.logger.warning(
                "%s: invalid declination value %s. It is assumed that the value has not been set." %
                (rec_id, dec)
            )
            return None

        if dec < -90 or dec > 90:
            raise ImportException("%s: declination must be between -90 and 90 instead of %s." % (rec_id, dec))

        return dec

    def _parse_ra(self, rec, rec_id):
        ra = rec.strip()
        if '' == ra:
            return None

        try:
            ra = float(ra)
        except ValueError:
            raise ImportException("%s: invalid right ascension value %s." % (rec_id, ra))

        if 999.0 == ra:
            self.logger.warning(
                "%s: invalid right ascension value %s. It is assumed that the value has not been set." %
                (rec_id, ra)
            )
            return None

        if ra < 0 or ra > 360:
            raise ImportException("%s: right ascension must be between 0 and 360 instead of %s." % (rec_id, ra))

        return ra

    @staticmethod
    def _parse_date_time(rec, ctx, obs_id):
        dt = rec.strip()
        if '' == dt:
            raise ImportException("%s: %s must be set." % (obs_id, ctx))

        try:
            dt = datetime.strptime(dt, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            raise ImportException("%s: invalid %s value %s." % (obs_id, ctx, dt))

        return dt

    @staticmethod
    def _validate_date(month, day, iau_code, ctx=''):

        if '' != ctx:
            ctx = 'of %s ' % ctx

        if day < 1 or day > 31:
            raise ImportException("%s: the day %smust be between 1 and 31 instead of %s" % (iau_code, ctx, day))

        if 31 == day and month in [4, 6, 9, 11]:
            raise ImportException("%s: the day %smust not be 31. The value is %s." % (iau_code, ctx, day))

        if 2 == month and day in [29, 30]:
            raise ImportException("%s: the day %smust not be 29 or 30. The value is %s." % (iau_code, ctx, day))

        return [month, day]

    def _check_period(self, period_start, period_end, max_period_duration,  obs_id):
        logger = self.logger
        if period_start == period_end:
            logger.warning(
                "%s: The observation has an incorrect time period. The beginning is equal to the end." % obs_id
            )
            return period_start, period_end

        diff = period_end - period_start
        if period_end > period_start and diff > max_period_duration:
            raise ImportException(
                "%s: The time period of observation is too long (%s - %s)." %
                (obs_id, str(period_start), str(period_end))
            )

        if period_end > period_start:
            return period_start, period_end

        diff = abs(diff)
        max_diff = timedelta(1)
        if diff > max_diff:
            raise ImportException(
                "%s: The observation has an wrong time period (%s - %s)." %
                (obs_id, str(period_start), str(period_end))
            )

        period_end += max_diff
        logger.warning(
            "%s: The observation has an incorrect time period. An attempt is made to correct it with (%s - %s)." %
            (obs_id, str(period_start), str(period_end))
        )

        return self._check_period(period_start, period_end, max_period_duration, obs_id)
