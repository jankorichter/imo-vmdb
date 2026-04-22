import importlib
import sys

_COMMANDS = {
    'cleanup':    ('imo_vmdb.command.cleanup',    'main'),
    'export':     ('imo_vmdb.command.export',     'main'),
    'initdb':     ('imo_vmdb.command.initdb',     'main'),
    'import_csv': ('imo_vmdb.command.import_csv', 'main'),
    'normalize':  ('imo_vmdb.command.normalize',  'main'),
    'web_server': ('imo_vmdb.webui.server',       'main'),
}


def usage():
    print('''Syntax: command <options>
Valid commands are:
    initdb      ... Initializes the database.
    cleanup     ... Removes data that are no longer needed.
    import_csv  ... Imports CSV files.
    normalize   ... Normalize and analyze meteor observations.
    export      ... Export data as CSV.
    web_server  ... Start the web server (Web UI and REST API).''')


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]
    if command not in _COMMANDS:
        usage()
        sys.exit(1)

    module_path, func_name = _COMMANDS[command]
    module = importlib.import_module(module_path)
    getattr(module, func_name)(sys.argv[2:])


if __name__ == "__main__":
    main()
