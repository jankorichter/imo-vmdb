"""HTTP-level tests for /health and the architecture invariant that the
REST layer only depends on imo_vmdb's public API.

OpenAPI-spec tests live in :mod:`tests.test_rest_openapi`.
"""

import ast
from pathlib import Path

_BASE = "/api/v1"


class TestHealth:
    def test_ok_with_db(self, client):
        r = client.get(f"{_BASE}/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_503_without_db(self, no_db_client):
        r = no_db_client.get(f"{_BASE}/health")
        assert r.status_code == 503
        assert r.get_json()["status"] == "degraded"


class TestRestApiArchitecture:
    """Guard: ``imo_vmdb/restapi.py`` must only import from ``imo_vmdb`` (the
    package's public API), not from internal submodules like ``imo_vmdb.query``
    or ``imo_vmdb.db``.  Standard library and third-party imports are allowed.
    """

    def test_no_internal_imo_vmdb_imports(self):
        path = Path(__file__).parent.parent / "imo_vmdb" / "restapi.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod.startswith("imo_vmdb."):
                    violations.append(f"from {mod} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("imo_vmdb."):
                        violations.append(f"import {alias.name}")
        assert not violations, (
            "REST layer must only import from the imo_vmdb package's public "
            f"API, but found: {violations}"
        )

    def test_uses_only_public_api_symbols(self):
        """Symbols imported from ``imo_vmdb`` must all appear in ``__all__``."""
        import imo_vmdb

        path = Path(__file__).parent.parent / "imo_vmdb" / "restapi.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "imo_vmdb":
                for alias in node.names:
                    imported.add(alias.name)
        unknown = imported - set(imo_vmdb.__all__)
        assert (
            not unknown
        ), f"restapi.py imports non-public symbols from imo_vmdb: {unknown}"
