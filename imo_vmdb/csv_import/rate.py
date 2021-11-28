from datetime import timedelta
from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class RateParser(CsvParser):

    _required_columns = {
        'rate id',
        'user id',
        'obs session id',
        'start date',
        'end date',
        'ra',
        'decl',
        'teff',
        'f',
        'lm',
        'shower',
        'method',
        'number'
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._logger = self._logger_factory.get_logger('rate import')
        self._insert_stmt = self._db_conn.convert_stmt('''
            INSERT INTO imported_rate (
                id,
                observer_id,
                session_id,
                "start",
                "end",
                t_eff,
                f,
                lm,
                ra,
                dec,
                shower,
                method,
                "number"
            ) VALUES (
                %(id)s,
                %(observer_id)s,
                %(session_id)s,
                %(start)s,
                %(end)s,
                %(t_eff)s,
                %(f)s,
                %(lm)s,
                %(ra)s,
                %(dec)s,
                %(shower)s,
                %(method)s,
                %(number)s
            )
        ''')

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn.convert_stmt('DELETE FROM imported_rate'))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        row = dict(zip(self.column_names, row))

        try:
            rate_id = self._parse_rate_id(row['rate id'])
            session_id = self._parse_session_id(row['obs session id'], rate_id)
            observer_id = self._parse_observer_id(row['user id'], row['user id'], session_id)
            shower = self._parse_shower(row['shower'])
            period_start = self._parse_date_time(row['start date'], 'start date', rate_id, session_id)
            period_end = self._parse_date_time(row['end date'], 'end date', rate_id, session_id)
            period_start, period_end = self._check_period(
                period_start,
                period_end,
                timedelta(days=0.49),
                rate_id,
                session_id
            )
            t_eff = self._parse_t_eff(row['teff'], rate_id, session_id)
            f = self._parse_f(row['f'], rate_id, session_id)
            freq = self._parse_freq(row['number'], rate_id, session_id)
            lm = self._parse_lm(row['lm'], rate_id, session_id)
            ra = self._parse_ra(row['ra'], rate_id, session_id)
            dec = self._parse_dec(row['decl'], rate_id, session_id)
            ra, dec = self._check_ra_dec(ra, dec, rate_id, session_id)
        except ImportException as err:
            self._log_error(str(err))
            return False

        record = {
            'id': rate_id,
            'observer_id': observer_id,
            'session_id': session_id,
            'start': period_start,
            'end': period_end,
            't_eff': t_eff,
            'f': f,
            'lm': lm,
            'shower': shower,
            'method': row['method'],
            'number': freq,
            'ra': ra,
            'dec': dec,
        }

        try:
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_rate_id(value):
        rate_id = value.strip()
        if '' == rate_id:
            raise ImportException('Observation found without a rate id.')

        try:
            rate_id = int(rate_id)
        except ValueError:
            raise ImportException('ID %s: invalid rate id.' % rate_id)
        if rate_id < 1:
            raise ImportException('ID %s: rate ID must be greater than 0.' % rate_id)

        return rate_id

    def _parse_t_eff(self, value, rate_id, session_id):
        t_eff = value.strip()
        if '' == t_eff:
            raise ImportException(
                'ID %s in session %s: t_eff must be set.' %
                (rate_id, session_id)
            )

        try:
            t_eff = float(t_eff)
        except ValueError:
            raise ImportException(
                'ID %s in session %s: invalid t_eff. The value is %s.' %
                (rate_id, session_id, t_eff)
            )

        if 0.0 == t_eff:
            raise ImportException(
                'ID %s in session %s: t_eff is 0.' %
                (rate_id, session_id)
            )

        if t_eff < 0.0:
            raise ImportException(
                'ID %s in session %s: t_eff must be greater than 0 instead of %s.' %
                (rate_id, session_id, t_eff)
            )

        if t_eff > 24.0:
            raise ImportException(
                'ID %s in session %s: t_eff must be less than 24 instead of %s.' %
                (rate_id, session_id, t_eff)
            )

        if not self._is_permissive and t_eff > 7.0:
            raise ImportException(
                'ID %s in session %s: t_eff must be less than 6 instead of %s.' %
                (rate_id, session_id, t_eff)
            )

        return t_eff

    @staticmethod
    def _parse_f(value, rate_id, session_id):
        f = value.strip()
        if '' == f:
            raise ImportException(
                'ID %s in session %s: f must be set.' %
                (rate_id, session_id)
            )

        try:
            f = float(f)
        except ValueError:
            raise ImportException(
                'ID %s in session %s: invalid f. The value is %s.' %
                (rate_id, session_id, f)
            )

        if f < 1.0:
            raise ImportException(
                'ID %s in session %s: f must be greater than 1 instead of %s.' %
                (rate_id, session_id, f)
            )

        return f

    @staticmethod
    def _parse_freq(value, rate_id, session_id):
        value = value.strip()

        try:
            value = int(value)
        except ValueError:
            raise ImportException(
                'ID %s in session %s: %s is an invalid count of meteors.' %
                (rate_id, session_id, value)
            )

        if value < 0:
            raise ImportException(
                'ID %s in session %s: count of meteors must be greater than 0 instead of %s.' %
                (rate_id, session_id, value)
            )

        return value

    @staticmethod
    def _parse_lm(value, rate_id, session_id):
        lm = value.strip()
        if '' == lm:
            raise ImportException(
                'ID %s in session %s: limiting magnitude must be set.' %
                (rate_id, session_id)
            )

        try:
            lm = float(lm)
        except ValueError:
            raise ImportException(
                'ID %s in session %s: invalid limiting magnitude. The value is %s.' %
                (rate_id, session_id, lm)
            )

        if lm < 0.0 or lm > 8:
            raise ImportException(
                'ID %s in session %s: lm must be between 0 and 8 instead of %s.' %
                (rate_id, session_id, lm)
            )

        return lm
