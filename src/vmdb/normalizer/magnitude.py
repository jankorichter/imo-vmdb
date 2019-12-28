import json


class Magnitude(object):

    def __init__(self, conn, solarlongs):
        self._conn = conn
        self._solarlongs = solarlongs

    def __call__(self, drop_tables, process_count, mod):
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
            FROM imported_magn as m
            INNER JOIN imported_session as s ON s.id = m.session_id
            WHERE
                m."start" < m."end" AND
                m.id %% %s = %s
        ''', (process_count, mod))

        column_names = [desc[0] for desc in cur.description]
        insert_stmt = '''
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
                %(magn_id)s,
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

        insert_detail_stmt = '''
            INSERT INTO magnitude_detail (
                id,
                magn,
                freq
            ) VALUES (
                %(magn_id)s,
                %(magn)s,
                %(freq)s
            )
        '''

        write_cur = self._conn.cursor()
        for record in cur:
            record = dict(zip(column_names, record))

            if not drop_tables:
                write_cur.execute('DELETE FROM magnitude WHERE id = %s', (record['id'],))

            magn_dict = json.loads(record['magn'])
            freq = int(sum(m for m in magn_dict.values()))
            if 0 == freq:
                continue

            mean = sum(float(m) * float(n) for m, n in magn_dict.items()) / freq
            sl_start = solarlongs.get(record['start'])
            sl_end = solarlongs.get(record['end'])
            iau_code = record['shower']
            iau_code = None if iau_code == 'SPO' else iau_code

            magn = {
                'shower': iau_code,
                'period_start': record['start'],
                'period_end': record['end'],
                'sl_start': sl_start,
                'sl_end': sl_end,
                'magn_id': record['id'],
                'session_id': record['session_id'],
                'observer_id': record['user_id'],
                'freq': freq,
                'mean': mean,
            }
            write_cur.execute(insert_stmt, magn)

            for m, n in magn_dict.items():
                magn = {
                    'magn_id': record['id'],
                    'magn': int(m),
                    'freq': float(n),
                }
                write_cur.execute(insert_detail_stmt, magn)

        cur.close()
        write_cur.close()
