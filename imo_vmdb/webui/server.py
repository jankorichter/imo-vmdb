import argparse
import os
import tempfile

from imo_vmdb.command import config_factory
from imo_vmdb.webui import create_app


def main(args=None):
    parser = argparse.ArgumentParser(description='imo-vmdb web server (Web UI and REST API)')
    parser.add_argument(
        '-c', '--config',
        dest='config_file',
        help='Path to the configuration file (or set IMO_VMDB_CONFIG env var)',
    )
    parser.add_argument('--host', default='127.0.0.1', help='Bind host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=None,
                        help='Bind port (default: 8000, or IMO_VMDB_WEBUI_PORT env var)')
    options = parser.parse_args(args)

    config = config_factory(options, parser)

    port = options.port if options.port is not None else config.getint('webui', 'port', fallback=8000)
    upload_dir = config.get('webui', 'upload_dir', fallback=tempfile.gettempdir())
    os.makedirs(upload_dir, exist_ok=True)

    print(f' * imo-vmdb web server running on http://{options.host}:{port}')

    app = create_app(config, upload_dir)
    app.run(host=options.host, port=port, threaded=True)


if __name__ == '__main__':
    main()
