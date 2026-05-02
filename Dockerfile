FROM python:3.10-slim

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
COPY imo_vmdb/ imo_vmdb/
COPY docs/ docs/

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --extras docs && \
    poetry run sphinx-build -b html docs imo_vmdb/built_docs && \
    python -m compileall -q imo_vmdb/

ENTRYPOINT ["python", "-m", "imo_vmdb"]
CMD ["web_server", "--host", "0.0.0.0"]
