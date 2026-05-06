import sys
from unittest.mock import patch

import pytest

from imo_vmdb.__main__ import main


def test_web_server_dispatches_to_httpd(monkeypatch):
    """web_server command must resolve to imo_vmdb.httpd:main."""
    monkeypatch.setattr(sys, "argv", ["imo_vmdb", "web_server", "--help"])
    with patch("imo_vmdb.httpd.main") as mock_main:
        main()
        mock_main.assert_called_once_with(["--help"])


def test_unknown_command_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["imo_vmdb", "nonexistent"])
    with pytest.raises(SystemExit):
        main()


def test_no_command_exits(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["imo_vmdb"])
    with pytest.raises(SystemExit):
        main()
