"""Tests for the OpenAPI specification served at /api/v1/openapi.{yaml,json}.

Covers:

* HTTP-level: both endpoints respond with 200 and the correct Content-Type,
  and the JSON payload is structurally valid OpenAPI.
* Schema validity: the YAML on disk parses and validates against the
  OpenAPI 3.1 schema.
* Drift detection: every Flask route under ``/api/v1`` is documented in
  the YAML, and every documented path is actually served.
"""

import json
import re
from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate

_BASE = "/api/v1"
_OPENAPI_FILE = Path(__file__).parent.parent / "docs" / "openapi.yaml"


@pytest.fixture(scope="session")
def openapi_spec():
    """Load the OpenAPI YAML once per test session."""
    with open(_OPENAPI_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


class TestOpenApiYaml:
    def test_returns_200(self, client):
        r = client.get(f"{_BASE}/openapi.yaml")
        assert r.status_code == 200
        assert r.content_type == "application/yaml"


class TestOpenApiJson:
    def test_returns_200(self, client):
        r = client.get(f"{_BASE}/openapi.json")
        assert r.status_code == 200
        assert r.content_type == "application/json"

    def test_payload_is_valid_json_with_openapi_key(self, client):
        spec = json.loads(client.get(f"{_BASE}/openapi.json").data)
        assert "openapi" in spec
        assert "paths" in spec


# ---------------------------------------------------------------------------
# Schema validity (OpenAPI 3.1)
# ---------------------------------------------------------------------------


class TestOpenApiSpecValidity:
    """Validates ``docs/openapi.yaml`` against the OpenAPI 3.1 specification.

    Catches: invalid ``$ref`` targets, missing required keys, wrong types,
    structural mistakes a hand-edit could introduce.
    """

    def test_yaml_parses(self, openapi_spec):
        # Sanity: the fixture itself proves YAML parses; assert the basics.
        assert openapi_spec["openapi"].startswith("3.")
        assert "paths" in openapi_spec
        assert "components" in openapi_spec

    def test_validates_against_openapi_3_1(self, openapi_spec):
        # Raises OpenAPIValidationError on any structural problem.
        validate(openapi_spec)


# ---------------------------------------------------------------------------
# Drift detection: Flask routes vs. documented paths
# ---------------------------------------------------------------------------


def _normalize(path: str) -> str:
    """Reduce any path parameter (Flask ``<...>`` or OpenAPI ``{...}``) to ``{}``.

    This lets us compare Flask routes and OpenAPI paths regardless of the
    parameter naming convention on either side.
    """
    return re.sub(r"<[^>]+>|\{[^}]+\}", "{}", path)


class TestOpenApiRouteDrift:
    """Guards: every ``/api/v1/*`` Flask route is in the YAML, and every
    documented path is actually served.

    Path-parameter names need not match between Flask and the YAML — only
    the *shape* of each path is compared.
    """

    def _flask_paths(self, app) -> set[str]:
        result = set()
        for rule in app.url_map.iter_rules():
            if rule.rule.startswith(f"{_BASE}/"):
                stripped = rule.rule[len(_BASE) :]
                result.add(_normalize(stripped))
        return result

    def _spec_paths(self, openapi_spec) -> set[str]:
        return {_normalize(p) for p in openapi_spec["paths"]}

    def test_every_flask_route_is_documented(self, app, openapi_spec):
        missing = self._flask_paths(app) - self._spec_paths(openapi_spec)
        assert not missing, (
            f"Flask serves these /api/v1 routes but OpenAPI YAML does not "
            f"document them: {sorted(missing)}"
        )

    def test_every_documented_path_is_served(self, app, openapi_spec):
        extra = self._spec_paths(openapi_spec) - self._flask_paths(app)
        assert not extra, (
            f"OpenAPI YAML documents these paths but Flask does not serve "
            f"them: {sorted(extra)}"
        )
