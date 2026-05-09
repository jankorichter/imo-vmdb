FROM python:3.10-slim

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY imo_vmdb/ imo_vmdb/
COPY docs/ docs/
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --extras docs --extras web && \
    poetry run sphinx-build -b html docs imo_vmdb/built_docs && \
    python -m compileall -q imo_vmdb/ && \
    chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
