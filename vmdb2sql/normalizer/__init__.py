from vmdb2sql.db import DBException

class BaseNormalizer(object):

    def __init__(self, db_conn, logger):
        self._db_conn = db_conn
        self._logger = logger
        self.has_errors = False
        self.counter_read = 0
        self.counter_write = 0

    def _log_error(self, msg):
        self._logger.error(msg)
        self.has_errors = True


def create_rate_magn(db_conn):
    try:
        cur = db_conn.cursor()
        # find magnitude-rate-pairs containing each other
        cur.execute(db_conn.convert_stmt('''
            WITH selection AS (
                SELECT
                    r.id as rate_id,
                    m.id as magn_id,
                    r.period_start as rate_period_start,
                    r.period_end as rate_period_end,
                    m.period_start as magn_period_start,
                    m.period_end as magn_period_end,
                    r.freq as rate_n,
                    m.freq as magn_n
                FROM rate as r
                INNER JOIN magnitude as m
                    ON
                       r.session_id = m.session_id AND
                       (
                           r.shower = m.shower OR
                           (r.shower IS NULL AND m.shower IS NULL)
                       )
            ),
            rate_magnitude_rel AS (
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    true as "equals"
                FROM selection
                WHERE
                   rate_period_start = magn_period_start AND
                   rate_period_end = magn_period_end
                UNION
                SELECT
                    rate_id,
                    magn_id,
                    rate_n,
                    magn_n,
                    false as "equals"
                FROM selection
                WHERE
                    -- magnitude period contains rate period
                    rate_period_start BETWEEN magn_period_start AND magn_period_end AND
                    rate_period_end BETWEEN magn_period_start AND magn_period_end AND
                    NOT (
                        -- rate period contains magnitude period
                        magn_period_start BETWEEN rate_period_start AND rate_period_end AND
                        magn_period_end BETWEEN rate_period_start AND rate_period_end
                    )
            ),
            aggregates AS (
                SELECT
                    rate_id,
                    magn_id,
                    sum(rate_n) OVER (PARTITION BY magn_id) as rate_n,
                    magn_n,
                    "equals",
                    count(magn_id) OVER (PARTITION BY rate_id) as magn_id_count
                FROM rate_magnitude_rel
            ),
            unique_rate_ids AS (
                SELECT
                    rate_id,
                    magn_id,
                    "equals"
                FROM aggregates
                WHERE
                    magn_id_count = 1 AND
                    rate_n = magn_n
            )
    
            SELECT rate_id, magn_id, "equals" FROM unique_rate_ids
        '''))
    except Exception as e:
        raise DBException(str(e))

    column_names = [desc[0] for desc in cur.description]
    insert_stmt = db_conn.convert_stmt('''
        INSERT INTO rate_magnitude (
            rate_id,
            magn_id,
            "equals"
        ) VALUES (
            %(rate_id)s,
            %(magn_id)s,
            %(equals)s
        )
    ''')

    try:
        write_cur = db_conn.cursor()
    except Exception as e:
        raise DBException(str(e))

    for record in cur:
        record = dict(zip(column_names, record))
        magn_rate = {
            'rate_id': record['rate_id'],
            'magn_id': record['magn_id'],
            'equals': record['equals'],
        }
        try:
            write_cur.execute(insert_stmt, magn_rate)
        except Exception as e:
            raise DBException(str(e))

    # set limiting mggnitude
    try:
        cur.execute(db_conn.convert_stmt('UPDATE magnitude SET lim_mag = NULL'))
        cur.execute(db_conn.convert_stmt('''
            WITH limiting_magnitudes AS (
                SELECT rm.magn_id, sum(r.t_eff*r.lim_mag)/sum(r.t_eff) as lim_mag
                FROM rate r
                INNER JOIN rate_magnitude rm ON rm.rate_id = r.id
                GROUP BY rm.magn_id
            )
            SELECT magn_id, round(lim_mag*100)/100.0 as lim_mag
            FROM limiting_magnitudes
        '''))
    except Exception as e:
        raise DBException(str(e))

    column_names = [desc[0] for desc in cur.description]
    update_stmt = db_conn.convert_stmt(
        'UPDATE magnitude SET lim_mag = %(lim_mag)s WHERE id = %(magn_id)s'
    )
    for record in cur:
        record = dict(zip(column_names, record))
        try:
            write_cur.execute(update_stmt, {
                'lim_mag': record['lim_mag'],
                'magn_id': record['magn_id']
            })
        except Exception as e:
            raise DBException(str(e))

    try:
        write_cur.close()
        cur.close()
    except Exception as e:
        raise DBException(str(e))