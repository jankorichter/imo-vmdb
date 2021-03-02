import sys


def usage():
    print('''Syntax: command <options>
Valid commands are:
    initdb      ... Initializes the database.
    cleanup     ... Removes data that are no longer needed.
    import_csv  ... Imports CSV files.
    normalize   ... Normalize and analyze meteor observations.''')


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]
    valid_commands = [
        'cleanup',
        'initdb',
        'import_csv',
        'normalize',
    ]

    if command not in valid_commands:
        usage()
        sys.exit(1)

    module = __import__(__package__)
    method_to_call = getattr(module, command)
    method_to_call(sys.argv[2:])


if __name__ == "__main__":
    main()
