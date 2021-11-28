import json
import math
from datetime import timedelta
from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class MagnitudesParser(CsvParser):

    _required_columns = {
        'magnitude id',
        'user id',
        'obs session id',
        'shower',
        'start date',
        'end date',
        'mag n6',
        'mag n5',
        'mag n4',
        'mag n3',
        'mag n2',
        'mag n1',
        'mag 0',
        'mag 1',
        'mag 2',
        'mag 3',
        'mag 4',
        'mag 5',
        'mag 6',
        'mag 7'
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._logger = self._logger_factory.get_logger('magnitudes import')
        self._insert_stmt = self._db_conn.convert_stmt('''
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
        ''')

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn.convert_stmt('DELETE FROM imported_magnitude'))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        row = dict(zip(self.column_names, row))

        try:
            magn_id = self._parse_magn_id(row['magnitude id'])
            session_id = self._parse_session_id(row['obs session id'], magn_id)
            observer_id = self._parse_observer_id(row['user id'], row['user id'], session_id)
            shower = self._parse_shower(row['shower'])
            period_start = self._parse_date_time(row['start date'], 'start date', magn_id, session_id)
            period_end = self._parse_date_time(row['end date'], 'end date', magn_id, session_id)
            period_start, period_end = self._check_period(
                period_start,
                period_end,
                timedelta(days=0.49),
                magn_id,
                session_id
            )
        except ImportException as err:
            self._log_error(str(err))
            return False

        magn = {}
        try:
            for column in range(1, 7):
                n = float(row['mag n' + str(column)])
                magn[str(-column)] = n

            for column in range(0, 8):
                n = float(row['mag ' + str(column)])
                magn[str(column)] = n
        except ValueError:
            self._log_error(
                'ID %s in session %s: Invalid count value of magnitudes found.' %
                (magn_id, session_id)
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
            'id': magn_id,
            'observer_id': observer_id,
            'session_id': session_id,
            'shower': shower,
            'start': period_start,
            'end': period_end,
            'magn': magn
        }

        try:
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_magn_id(value):
        magn_id = value.strip()
        if '' == magn_id:
            raise ImportException('Observation found without a magnitude id.')

        try:
            magn_id = int(magn_id)
        except ValueError:
            raise ImportException('ID %s: invalid magnitude id.' % magn_id)
        if magn_id < 1:
            raise ImportException('ID %s: magnitude ID must be greater than 0.' % magn_id)

        return magn_id

    @staticmethod
    def _validate_count(n, m, magn_id, session_id):
        if n < 0.0:
            raise ImportException(
                'ID %s in session %s: Invalid count %s found for a meteor magnitude of %s.' %
                (magn_id, session_id, n, m)
            )

        n_cmp = math.floor(n)
        if n == n_cmp:
            return

        n_cmp += 0.5
        if n == n_cmp:
            return

        raise ImportException(
            'ID %s in session %s: Invalid count %s found for a meteor magnitude of %s.' %
            (magn_id, session_id, n, m))

    def _validate_total_count(self, magn, magn_id, session_id):
        is_permissive = self._is_permissive
        n_sum = 0
        for m in sorted(magn.keys(), key=int):
            n = magn[m]
            n_sum += n
            if not is_permissive and 0 == n and math.floor(n_sum) != n_sum:
                raise ImportException(
                    'ID %s in session %s: Inconsistent total count of meteors found.' %
                    (magn_id, session_id)
                )

        if math.floor(n_sum) != n_sum:
            raise ImportException(
                'ID %s in session %s: The count of meteors out of a total of %s is invalid.' %
                (magn_id, session_id, n_sum)
            )
