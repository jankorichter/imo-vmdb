import importlib
import re


class DBAdapter(object):

    def __init__(self, config):
        self.db_module = config['module']
        db = importlib.import_module(self.db_module)
        self.conn = db.connect(**config['connection'])
        if 'sqlite3' == self.db_module:
            self.conn.execute('PRAGMA foreign_keys = ON')

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
