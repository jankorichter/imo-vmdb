import importlib
import re
import warnings
from datetime import timedelta


class DBAdapter(object):

    def __init__(self, config):
        self.db_module = config['module']
        db = importlib.import_module(self.db_module)
        self.conn = db.connect(**config['connection'])

    def cursor(self):
        return self.conn.cursor()

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

    def convert_stmt(self, stmt):
        if 'sqlite3' == self.db_module:
            stmt = stmt.replace(' %% ', ' % ')
            return re.sub('%\\(([^)]*)\\)s', ':\\1', stmt)

        return stmt


def custom_formatwarning(msg, *args, **kwargs):
    # ignore everything except the message
    return str(msg) + '\n'


def check_period(obs_id, period_start, period_end, max_period_duration):
    if period_start == period_end:
        warnings.warn("Observation %s has a wrong period. Start equals end. Ignored." % (obs_id,))
        return period_start, period_end

    diff = period_end - period_start
    if period_end > period_start and diff > max_period_duration:
        warnings.warn(
            "Period of observation %s is too long (%s - %s). Discarded." % (obs_id, str(period_start), str(period_end)))
        return None, None

    if period_end > period_start:
        return period_start, period_end

    max_diff = timedelta(1)
    diff = abs(diff)
    if diff > max_diff:
        warnings.warn(
            "Observation %s has a wrong period (%s - %s). Discarded." % (obs_id, str(period_start), str(period_end)))
        return None, None

    period_end += max_diff
    msg_args = (obs_id, str(period_start), str(period_end))
    warnings.warn("Observation %s has a wrong period. Trying to fix it with %s - %s." % msg_args)

    return check_period(obs_id, period_start, period_end, max_period_duration)
