"""The package exports what it states, and imports without the security core.

The dev group installs xtr-security-core, so every other test runs with it
there; only a fresh interpreter that cannot import it shows the guard
context, the guard expression and the audit trail do not need it.
"""

from __future__ import annotations

import subprocess
import sys

import xtr_workflow.event_listener

WITHOUT_THE_SECURITY_CORE = """
import importlib
import sys

sys.modules["xtr_security_core"] = None

try:
    importlib.import_module("xtr_security_core")
except ModuleNotFoundError:
    pass
else:
    raise AssertionError("a blanked module stayed importable: this run proves nothing")

import xtr_workflow.event_listener
"""


def test_exports_are_declared() -> None:
    package = xtr_workflow.event_listener
    missing = [name for name in package.__all__ if not hasattr(package, name)]

    assert type(package.__all__) is list
    assert missing == []


def test_it_imports_without_the_security_core() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", WITHOUT_THE_SECURITY_CORE],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
