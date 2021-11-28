from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class RadiantParser(CsvParser):

    _required_columns = {
        'shower',
        'ra',
        'dec',
        'day',
        'month'
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._logger = self._logger_factory.get_logger('radiant import')
        self._insert_stmt = self._db_conn.convert_stmt('''
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
        ''')

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn.convert_stmt('DELETE FROM radiant'))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        row = dict(zip(self.column_names, row))

        try:
            shower = self._parse_shower(row['shower'])
            ra = self._parse_ra(row['ra'], shower)
            dec = self._parse_dec(row['dec'], shower)
            month = self._parse_int(row['month'], 'month', shower)
            day = self._parse_int(row['day'], 'day', shower)
            self._validate_date(month, day, shower)
            if ra is None or dec is None:
                raise ImportException('ID %s: ra and dec must be set.' % shower)

        except ImportException as err:
            self._log_error(str(err))
            return False

        record = {
            'shower': shower,
            'ra': ra,
            'dec': dec,
            'month': month,
            'day': day,
        }

        try:
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_shower(value):
        shower = value.strip()
        if '' == shower:
            raise ImportException("Shower code must not be empty.")

        return shower.upper()

    @staticmethod
    def _parse_int(value, ctx, iau_code):
        value = value.strip()

        try:
            value = int(value)
        except ValueError:
            raise ImportException("ID %s: %s is an invalid %s." % (iau_code, value, ctx))

        return value
