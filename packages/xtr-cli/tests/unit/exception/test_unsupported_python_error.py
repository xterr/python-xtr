from __future__ import annotations

from xtr_cli.exception import UnsupportedPythonError


def test_it_names_the_oldest_version_supported() -> None:
    assert "3.11 or later" in str(UnsupportedPythonError("3.9"))
