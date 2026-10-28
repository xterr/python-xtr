"""The package imports and runs without the optional packages, except where it must not.

The dev group installs every optional package, so every other test runs with
them there. Only a fresh interpreter that cannot import them shows that the
modules outside the bundle, the console command, the guard listener and the
recipe load none of them, and that the bundle is the place that needs one.
"""

from __future__ import annotations

import subprocess
import sys

BLOCKED = ("xtr_dependency_injection", "xtr_console", "xtr_security_core", "xtr_security")

BLOCK_OPTIONAL_PACKAGES = f"""
import sys

for name in {BLOCKED!r}:
    sys.modules[name] = None

try:
    import xtr_dependency_injection
except ImportError:
    pass
else:
    raise AssertionError("a blocked package stayed importable: this run proves nothing")
"""

IMPORT_EVERY_MODULE_AND_RUN = (
    BLOCK_OPTIONAL_PACKAGES
    + """
import asyncio
import importlib
import pkgutil

import xtr_workflow
from xtr_event_dispatcher import EventDispatcher
from xtr_workflow import Definition, Transition, Workflow
from xtr_workflow.marking_store import MethodMarkingStore

EXCLUDED = (
    "xtr_workflow.bundle",
    "xtr_workflow.command",
    "xtr_workflow.event_listener.guard_listener",
    "xtr_workflow.recipe",
)


def excluded(name):
    return any(name == prefix or name.startswith(prefix + ".") for prefix in EXCLUDED)


def on_error(name):
    if not excluded(name):
        raise ImportError(f"cannot discover {name} without the optional packages")


names = [
    info.name
    for info in pkgutil.walk_packages(xtr_workflow.__path__, "xtr_workflow.", onerror=on_error)
    if not excluded(info.name)
]
for name in names:
    importlib.import_module(name)


class Article:
    def __init__(self):
        self._marking = {"a": 1}

    def get_marking(self):
        return self._marking

    def set_marking(self, marking, context=None):
        self._marking = dict(marking)


async def run():
    dispatcher = EventDispatcher()
    workflow = Workflow(
        Definition(["a", "b"], [Transition("t1", "a", "b")]),
        MethodMarkingStore(),
        dispatcher,
        "article",
    )
    marking = await workflow.apply(Article(), "t1")
    if marking.get_places() != {"b": 1}:
        raise AssertionError(f"unexpected marking {marking.get_places()}")


asyncio.run(run())
print(f"IMPORTED {len(names)} MODULES; WORKFLOW APPLIED WITHOUT OPTIONAL PACKAGES")
"""
)

BUNDLE_NEEDS_DEPENDENCY_INJECTION = (
    BLOCK_OPTIONAL_PACKAGES
    + """
import importlib

try:
    importlib.import_module("xtr_workflow.bundle")
except ImportError as error:
    if error.name != "xtr_dependency_injection":
        raise
else:
    raise AssertionError("the bundle imported without the dependency injection package")
"""
)

MARKER = "IMPORTED"


def _run(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 -- a fixed script on sys.executable, nothing untrusted
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )


def test_every_module_outside_the_optional_ones_runs_without_them() -> None:
    completed = _run(IMPORT_EVERY_MODULE_AND_RUN)

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert MARKER in completed.stdout


def test_the_bundle_is_where_the_dependency_injection_package_is_needed() -> None:
    completed = _run(BUNDLE_NEEDS_DEPENDENCY_INJECTION)

    assert completed.returncode == 0, completed.stderr or completed.stdout
