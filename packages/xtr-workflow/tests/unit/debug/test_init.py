"""The package exports what it states, and its tools load none of the optional packages.

The dev group installs every optional package, so every other test runs with
them there; only a fresh interpreter shows that importing the debugging tools,
and listing a workflow's listeners, loads none of them — above all not the
security core, which only the guard listener needs.
"""

from __future__ import annotations

import subprocess
import sys

import xtr_workflow.debug

USE_THE_DEBUGGING_TOOLS = """
import sys

import anyio
from xtr_event_dispatcher import EventDispatcher

import xtr_workflow.debug
from xtr_workflow import Definition
from xtr_workflow.debug.listener_extractor import ListenerExtractor

dispatcher = EventDispatcher()
dispatcher.add_listener("workflow.leave", print)
anyio.run(ListenerExtractor(dispatcher).extract_listeners, "article", Definition(["a"], []))

OPTIONAL = ("xtr_console", "xtr_dependency_injection", "xtr_security", "xtr_security_core")
loaded = [name for name in OPTIONAL if name in sys.modules]
if loaded:
    raise AssertionError(f"the debugging tools loaded {loaded}")
"""


def test_exports_are_declared() -> None:
    package = xtr_workflow.debug
    missing = [name for name in package.__all__ if not hasattr(package, name)]

    assert type(package.__all__) is list
    assert missing == []


def test_the_debugging_tools_load_no_optional_package() -> None:
    completed = subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", USE_THE_DEBUGGING_TOOLS],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
