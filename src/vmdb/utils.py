import sys
import importlib
import warnings
from datetime import timedelta


def connection_decorator(func):
    def f(*args, **kwargs):
        config = sys.modules[__name__].config
        db_config = config['database']
        db = importlib.import_module(db_config['module'])
        conn = db.connect(**db_config['connection'])
        kwargs['conn'] = conn
        func(*args, **kwargs)
        conn.commit()
        conn.close()

    return f


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
