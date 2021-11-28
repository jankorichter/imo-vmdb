from imo_vmdb.csv_import import CsvParser, ImportException
from imo_vmdb.db import DBException


class ShowerParser(CsvParser):

    _month_names = {
        None: None,
        'Jan': 1,
        'Feb': 2,
        'Mar': 3,
        'Apr': 4,
        'May': 5,
        'Jun': 6,
        'Jul': 7,
        'Aug': 8,
        'Sep': 9,
        'Oct': 10,
        'Nov': 11,
        'Dec': 12,
    }

    _required_columns = {
        'id',
        'iau_code',
        'name',
        'start',
        'end',
        'peak',
        'ra',
        'de',
        'v',
        'r',
        'zhr'
    }

    def __init__(self, *args, **kwars):
        super().__init__(*args, **kwars)
        self._logger = self._logger_factory.get_logger('shower import')
        self._insert_stmt = self._db_conn.convert_stmt('''
            INSERT INTO shower (
                id,
                iau_code,
                "name",
                start_month,
                start_day,
                end_month,
                end_day,
                peak_month,
                peak_day,
                ra,
                "dec",
                v,
                r,
                zhr
            ) VALUES (
                %(id)s,
                %(iau_code)s,
                %(name)s,
                %(start_month)s,
                %(start_day)s,
                %(end_month)s,
                %(end_day)s,
                %(peak_month)s,
                %(peak_day)s,
                %(ra)s,
                %(dec)s,
                %(v)s,
                %(r)s,
                %(zhr)s
            )
        ''')

    def on_start(self, cur):
        if self._do_delete:
            try:
                cur.execute(self._db_conn.convert_stmt('DELETE FROM shower'))
            except Exception as e:
                raise DBException(str(e))

    def parse_row(self, row, cur):
        row = dict(zip(self.column_names, row))

        try:
            iau_code = self._parse_iau_code(row['iau_code'])
            ra = self._parse_ra(row['ra'], iau_code)
            dec = self._parse_dec(row['de'], iau_code)
            v = self._parse_velocity(row['v'], iau_code)
            r = self._parse_r_value(row['r'], iau_code)
            peak = self._create_date(row['peak'], 'peak', iau_code)
            period_start = self._create_date(row['start'], 'start', iau_code)
            period_end = self._create_date(row['end'], 'end', iau_code)
            ra, dec = self._check_ra_dec(ra, dec, iau_code)
        except ImportException as err:
            self._log_error(str(err))
            return False

        shower_name = row['name'].strip()
        if 0 == len(shower_name):
            self._logger.warning("%s: name of shower is empty." % iau_code)

        zhr = row['zhr'].strip()
        record = {
            'id': int(row['id'].strip()),
            'iau_code': iau_code,
            'name': shower_name,
            'start_month': period_start[0],
            'start_day': period_start[1],
            'end_month': period_end[0],
            'end_day': period_end[1],
            'peak_month': peak[0],
            'peak_day': peak[1],
            'ra': ra,
            'dec': dec,
            'v': v,
            'r': r,
            'zhr': zhr if '' != zhr else None,
        }

        try:
            cur.execute(self._insert_stmt, record)
        except Exception as e:
            raise DBException(str(e))

        return True

    @staticmethod
    def _parse_iau_code(value):
        iau_code = value.strip()
        if '' == iau_code:
            raise ImportException("Shower found without an iau_code.")

        return iau_code.upper()

    @staticmethod
    def _parse_velocity(value, iau_code):
        v = value.strip()
        if '' == v:
            return None

        try:
            v = float(v)
        except ValueError:
            raise ImportException("ID %s: invalid velocity value. The value is %s." % (iau_code, v))

        if v < 11 or v > 75:
            raise ImportException("ID %s: velocity must be between 11 and 75 instead of %s." % (iau_code, v))

        return v

    @staticmethod
    def _parse_r_value(value, iau_code):
        r = value.strip()
        if '' == r:
            return None

        try:
            r = float(r)
        except ValueError:
            raise ImportException("ID %s: invalid r-value. The value is %s." % (iau_code, r))

        if r < 1 or r > 5:
            raise ImportException("ID %s: r-value must be between 1 and 5 instead of %s." % (iau_code, r))

        return r

    @classmethod
    def _create_date(cls, date_str, ctx, iau_code):
        date_str = date_str.strip()

        if '' == date_str:
            return [None, None]

        month_names = cls._month_names
        value = date_str.split()

        if len(value) != 2:
            raise ImportException(
                "ID %s: %s must have the the format MM/DD. The value is %s." %
                (iau_code, ctx, value)
            )

        if value[0] not in month_names:
            raise ImportException("ID %s: %s is an invalid month name. The value is %s." % (iau_code, value[0], ctx))

        month = month_names[value[0]]

        try:
            day = int(value[1])
        except ValueError:
            raise ImportException("ID %s: %s is an invalid day. The value is %s." % (iau_code, value[1], ctx))

        return cls._validate_date(month, day, iau_code, ctx)
