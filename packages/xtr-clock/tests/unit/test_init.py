from __future__ import annotations

import importlib
import pkgutil
import tomllib
from pathlib import Path
from typing import cast

import pytest

import xtr_clock

MODULES = sorted(name for _, name, _ in pkgutil.walk_packages(xtr_clock.__path__, "xtr_clock."))
PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_everything_it_advertises_can_be_reached() -> None:
    missing = [name for name in xtr_clock.__all__ if not hasattr(xtr_clock, name)]

    assert missing == []


def test_what_it_advertises_is_sorted() -> None:
    assert list(xtr_clock.__all__) == sorted(xtr_clock.__all__)


def test_it_advertises_no_name_twice() -> None:
    assert len(set(xtr_clock.__all__)) == len(xtr_clock.__all__)


@pytest.mark.skipif(not PYPROJECT.is_file(), reason="not a source checkout")
def test_the_version_it_reports_is_the_version_declared_once_in_pyproject() -> None:
    declared = cast(
        "str", tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    )

    assert xtr_clock.__version__ == declared


def test_the_version_is_read_rather_than_written_down_a_second_time() -> None:
    source = (Path(xtr_clock.__file__)).read_text(encoding="utf-8")

    assert f'"{xtr_clock.__version__}"' not in source


@pytest.mark.parametrize("module", MODULES)
def test_every_module_states_what_it_exports(module: str) -> None:
    assert hasattr(importlib.import_module(module), "__all__"), module


@pytest.mark.parametrize("module", MODULES)
def test_every_module_has_a_docstring(module: str) -> None:
    assert importlib.import_module(module).__doc__, module
