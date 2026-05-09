#!/bin/sh
set -e
if [ $# -eq 0 ]; then
    exec gunicorn \
        --workers 1 \
        --threads "${IMO_VMDB_WEBUI_THREADS:-4}" \
        --bind "${IMO_VMDB_WEBUI_HOST:-0.0.0.0}:${IMO_VMDB_WEBUI_PORT:-8000}" \
        "imo_vmdb.httpd:wsgi_app()"
fi
exec python -m imo_vmdb "$@"
