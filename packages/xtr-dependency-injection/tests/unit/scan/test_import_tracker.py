from __future__ import annotations

import builtins
import importlib
import importlib.util
import threading
from typing import TYPE_CHECKING, cast

import pytest

from xtr_dependency_injection.scan._import_tracker import ImportTracker

if TYPE_CHECKING:
    from tests.support.modules import ScratchModules


@pytest.fixture
def modules(scratch_modules: ScratchModules) -> ScratchModules:
    scratch_modules.write(
        {
            "acme_app.helpers": "VALUE = 1\n",
            "acme_app.absolute": "import acme_app.helpers\n",
            "acme_app.relative": "from . import helpers\n",
            "acme_app.named": "from acme_app.helpers import VALUE\n",
            "acme_app.deep.inner": "from .. import helpers\n",
            "acme_app.in_function": "def later():\n    import acme_app.helpers\n",
            "acme_app.calling": "from acme_app.in_function import later\n\nlater()\n",
        }
    )
    return scratch_modules


@pytest.mark.usefixtures("modules")
@pytest.mark.parametrize(
    ("importer", "reached"),
    [
        ("acme_app.absolute", {"acme_app.helpers"}),
        ("acme_app.relative", {"acme_app", "acme_app.helpers"}),
        ("acme_app.named", {"acme_app.helpers"}),
        ("acme_app.deep.inner", {"acme_app", "acme_app.helpers"}),
    ],
)
def test_it_records_what_an_import_statement_reached(importer: str, reached: set[str]) -> None:
    with ImportTracker() as tracker:
        _ = importlib.import_module(importer)

    # The import system's own imports, made while it loads a module, are credited there too.
    assert reached <= tracker.imports[importer]


@pytest.mark.usefixtures("modules")
def test_an_import_inside_a_function_is_credited_to_the_module_body_calling_it() -> None:
    with ImportTracker() as tracker:
        _ = importlib.import_module("acme_app.calling")

    assert "acme_app.helpers" in tracker.imports["acme_app.calling"]
    assert "acme_app.helpers" not in tracker.imports.get("acme_app.in_function", set())


def test_a_failed_import_is_not_recorded() -> None:
    with ImportTracker() as tracker, pytest.raises(ModuleNotFoundError):
        exec("import acme_not_installed", {"__name__": "acme_app.failing"})  # noqa: S102 — an import statement run under a module name of the test's own

    assert "acme_app.failing" not in tracker.imports


def test_an_import_given_no_globals_is_the_running_modules(
    scratch_modules: ScratchModules,
) -> None:
    scratch_modules.write({"acme_app.bare": "__import__('json')\n"})

    with ImportTracker() as tracker:
        _ = importlib.import_module("acme_app.bare")

    assert "json" in tracker.imports["acme_app.bare"]


def test_importlib_imports_and_lookups_are_recorded_for_the_running_module(
    scratch_modules: ScratchModules,
) -> None:
    scratch_modules.write(
        {
            "acme_app.helpers": "VALUE = 1\n",
            "acme_app.dynamic": (
                "import importlib\nimport importlib.util\n\n"
                "helpers = importlib.import_module('acme_app.helpers')\n"
                "FOUND = importlib.util.find_spec('acme_not_installed')\n"
            ),
        }
    )

    with ImportTracker() as tracker:
        _ = importlib.import_module("acme_app.dynamic")

    assert "acme_app.helpers" in tracker.imports["acme_app.dynamic"]
    # Asking whether a module exists is not reaching it: it is recorded apart.
    assert tracker.lookups["acme_app.dynamic"] == {"acme_not_installed"}
    assert "acme_not_installed" not in tracker.imports["acme_app.dynamic"]


def test_a_hook_installed_over_it_is_left_in_place_and_it_stops_recording() -> None:
    original = builtins.__import__
    outer = ImportTracker()
    inner = ImportTracker()

    _ = outer.__enter__()
    _ = inner.__enter__()
    outer.__exit__(None, None, None)
    inner.__exit__(None, None, None)

    # The inner tracker put back the outer one's hook, which now only passes calls on.
    _ = cast("object", builtins.__import__("json"))
    assert outer.imports == {}
    _ = outer.__enter__()
    outer.__exit__(None, None, None)
    assert builtins.__import__ is original


def test_a_relative_name_asked_about_is_recorded_absolute(
    scratch_modules: ScratchModules,
) -> None:
    scratch_modules.write(
        {
            "acme_app.helpers": "VALUE = 1\n",
            "acme_app.relative_probe": (
                "import importlib.util\n\n"
                "FOUND = importlib.util.find_spec('.helpers', 'acme_app')\n"
            ),
        }
    )

    with ImportTracker() as tracker:
        _ = importlib.import_module("acme_app.relative_probe")

    assert "acme_app.helpers" in tracker.lookups["acme_app.relative_probe"]


def test_trackers_given_one_record_add_to_it() -> None:
    shared: dict[str, set[str]] = {"acme_app.earlier": {"json"}}

    with ImportTracker(imports=shared) as tracker:
        exec("import json", {"__name__": "acme_app.later"})  # noqa: S102 — an import statement run under a module name of the test's own

    assert tracker.imports is shared
    assert shared == {"acme_app.earlier": {"json"}, "acme_app.later": {"json"}}


def test_the_after_callback_runs_when_an_import_fails() -> None:
    calls: list[None] = []

    with (
        ImportTracker(after=lambda: calls.append(None)),
        pytest.raises(ModuleNotFoundError),
    ):
        _ = cast("object", builtins.__import__("acme_not_installed"))

    assert calls == [None]


def test_imports_outside_any_module_body_are_not_recorded() -> None:
    tracker = ImportTracker()

    def outside() -> None:
        with tracker:
            _ = cast("object", builtins.__import__("json"))
            _ = importlib.import_module("json")
            _ = importlib.util.find_spec("json")

    thread = threading.Thread(target=outside)
    thread.start()
    thread.join()

    assert tracker.imports == {}


def test_an_import_outside_any_module_body_is_credited_to_the_globals_it_names() -> None:
    tracker = ImportTracker()

    def outside() -> None:
        with tracker:
            _ = cast("object", builtins.__import__("json", {"__name__": "acme_app.threaded"}))

    thread = threading.Thread(target=outside)
    thread.start()
    thread.join()

    assert tracker.imports == {"acme_app.threaded": {"json"}}


def test_another_threads_imports_are_neither_recorded_nor_called_back() -> None:
    calls: list[None] = []

    def elsewhere() -> None:
        _ = cast("object", builtins.__import__("json", {"__name__": "acme_app.threaded"}))
        _ = importlib.import_module("json")
        _ = importlib.util.find_spec("json")

    with ImportTracker(before=lambda: calls.append(None)) as tracker:
        thread = threading.Thread(target=elsewhere)
        thread.start()
        thread.join()

    assert tracker.imports == {}
    assert calls == []


def test_the_callback_runs_before_each_import_call_of_its_thread() -> None:
    calls: list[None] = []

    with ImportTracker(before=lambda: calls.append(None)):
        _ = cast("object", builtins.__import__("json"))
        _ = importlib.import_module("json")
        _ = importlib.util.find_spec("json")

    assert len(calls) == 3


def test_a_module_standing_in_for_itself_with_no_name_is_not_recorded(
    scratch_modules: ScratchModules,
) -> None:
    scratch_modules.write(
        {
            "acme_odd": (
                "import sys\n\n\nclass _Odd:\n    value = 1\n\n\nsys.modules[__name__] = _Odd()\n"
            ),
            "acme_app.odd_user": "from acme_odd import value\n",
        }
    )

    with ImportTracker() as tracker:
        _ = importlib.import_module("acme_app.odd_user")

    assert "acme_odd" not in tracker.imports.get("acme_app.odd_user", set())


def test_closing_puts_the_original_import_back() -> None:
    original = builtins.__import__

    with ImportTracker():
        assert builtins.__import__ is not original

    assert builtins.__import__ is original


def test_the_import_is_put_back_when_the_block_raises() -> None:
    original = builtins.__import__

    with pytest.raises(RuntimeError), ImportTracker():
        raise RuntimeError

    assert builtins.__import__ is original
