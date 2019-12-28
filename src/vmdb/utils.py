import sys
import importlib


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
