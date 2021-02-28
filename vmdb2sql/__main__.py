import sys


def usage():
    print('''Syntax: command <options>
Valid commands are:
    cleanup             ... Removes data that are no longer needed.
    generate_solarlongs ... Generates a solarlong lookup table.
    import_magnitudes   ... Imports magnitude observations.
    import_radiants     ... Imports radiant positions.
    import_rates        ... Imports rate observations.
    import_sessions     ... Imports observation sessions.
    import_showers      ... Imports meteor showers.
    normalize           ... Normalize and analyze meteor observations.''')


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)

    command = sys.argv[1]
    valid_commands = [
        'cleanup',
        'generate_solarlongs',
        'import_magnitudes',
        'import_radiants',
        'import_rates',
        'import_sessions',
        'import_showers',
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
