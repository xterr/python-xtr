from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import xtr_http_message
from xtr_http_message import exception, factory


def test_the_version_is_the_one_pyproject_declares() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    data = cast(
        "dict[str, dict[str, object]]",
        tomllib.loads(pyproject.read_text(encoding="utf-8")),
    )

    assert xtr_http_message.__version__ == data["project"]["version"]


def test_every_exported_name_resolves() -> None:
    missing = [name for name in xtr_http_message.__all__ if not hasattr(xtr_http_message, name)]

    assert missing == []


def test_every_name_the_factory_package_exports_resolves() -> None:
    missing = [name for name in factory.__all__ if not hasattr(factory, name)]

    assert missing == []


def test_every_name_the_exception_package_exports_resolves() -> None:
    missing = [name for name in exception.__all__ if not hasattr(exception, name)]

    assert missing == []


def test_the_errors_are_the_same_objects_at_either_import() -> None:
    reexported = [getattr(xtr_http_message, name) for name in exception.__all__]
    direct = [getattr(exception, name) for name in exception.__all__]

    assert reexported == direct


def test_the_factory_is_the_same_object_at_either_import() -> None:
    assert xtr_http_message.HttpFactory is factory.HttpFactory
