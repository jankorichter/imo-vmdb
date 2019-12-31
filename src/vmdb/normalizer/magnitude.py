import json
import warnings


class Record(object):
    _insert_stmt = '''
        INSERT INTO magnitude (
            id,
            shower,
            period_start,
            period_end,
            sl_start,
            sl_end,
            session_id,
            observer_id,
            freq,
            mean
        ) VALUES (
            %(id)s,
            %(shower)s,
            %(period_start)s,
            %(period_end)s,
            %(sl_start)s,
            %(sl_end)s,
            %(session_id)s,
            %(observer_id)s,
            %(freq)s,
            %(mean)s
        )
    '''

    _insert_detail_stmt = '''
        INSERT INTO magnitude_detail (
            id,
            magn,
            freq
        ) VALUES (
            %(id)s,
            %(magn)s,
            %(freq)s
        )
    '''

    def __init__(self, record):
        self.id = record['id']
        self.shower = record['shower']
        self.session_id = record['session_id']
        self.user_id = record['user_id']
        self.start = record['start']
        self.end = record['end']
        self.magn = json.loads(record['magn'])

    def __eq__(self, other):
        return not self != other

    def __ne__(self, other):
        if self.session_id != other.session_id:
            return True

        if self.shower != other.shower:
            return True

        if self.end <= other.start:
            return True

        if self.start >= other.end:
            return True

        return False

    def __contains__(self, other):
        if self != other:
            return False

        if self.start > other.start or self.end < other.end:
            return False

        return True

    def write(self, cur, solarlongs):
        mid = self.id
        freq = int(sum(m for m in self.magn.values()))
        magn_items = self.magn.items()
        mean = sum(float(m) * float(n) for m, n in magn_items) / freq
        sl_start = solarlongs.get(self.start)
        sl_end = solarlongs.get(self.end)
        iau_code = self.shower
        magn = {
            'id': mid,
            'shower': iau_code,
            'period_start': self.start,
            'period_end': self.end,
            'sl_start': sl_start,
            'sl_end': sl_end,
            'session_id': self.session_id,
            'observer_id': self.user_id,
            'freq': freq,
            'mean': mean,
        }
        cur.execute(self._insert_stmt, magn)

        for m, n in magn_items:
            magn = {
                'id': mid,
                'magn': int(m),
                'freq': float(n),
            }
            cur.execute(self._insert_detail_stmt, magn)


class Normalizer(object):

    def __init__(self, conn, solarlongs):
        self._conn = conn
        self._solarlongs = solarlongs

    def __call__(self, drop_tables, divisor, mod):
        solarlongs = self._solarlongs
        cur = self._conn.cursor()
        cur.execute('''
            SELECT
                m.id,
                m.shower,
                m.session_id,
                m.user_id,
                m."start",
                m."end",
                m.magn
            FROM imported_magnitude as m
            INNER JOIN imported_session as s ON s.id = m.session_id
            WHERE
                m.session_id %% %s = %s
            ORDER BY
                m.session_id ASC,
                m.shower ASC,
                m."start" ASC,
                m."end" DESC
        ''', (divisor, mod))

        column_names = [desc[0] for desc in cur.description]
        write_cur = self._conn.cursor()
        prev_record = None
        for _record in cur:
            record = Record(dict(zip(column_names, _record)))
            if not drop_tables:
                write_cur.execute('DELETE FROM magnitude WHERE id = %s', (record.id,))

            if prev_record is None:
                prev_record = record
                continue

            if record in prev_record:
                msg = "Magnitude observation %s contains observation %s. Observation %s discarded."
                warnings.warn(msg % (prev_record.id, record.id, prev_record.id))
                prev_record = record
                continue

            if prev_record == record:
                msg = "Magnitude observation %s overlaps observation %s. Observation %s discarded."
                warnings.warn(msg % (prev_record.id, record.id, record.id))
                continue

            prev_record.write(write_cur, solarlongs)
            prev_record = record

        if prev_record is not None:
            prev_record.write(write_cur, solarlongs,)

        cur.close()
        write_cur.close()
