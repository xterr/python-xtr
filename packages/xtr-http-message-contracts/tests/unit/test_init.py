from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import xtr_http_message_contracts
from xtr_http_message_contracts import factory


def test_the_version_is_the_one_pyproject_declares() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    data = cast(
        "dict[str, dict[str, object]]",
        tomllib.loads(pyproject.read_text(encoding="utf-8")),
    )

    assert xtr_http_message_contracts.__version__ == data["project"]["version"]


def test_every_exported_name_resolves() -> None:
    missing = [
        name
        for name in xtr_http_message_contracts.__all__
        if not hasattr(xtr_http_message_contracts, name)
    ]

    assert missing == []


def test_every_name_the_factory_package_exports_resolves() -> None:
    missing = [name for name in factory.__all__ if not hasattr(factory, name)]

    assert missing == []


def test_the_factories_are_the_same_objects_at_either_import() -> None:
    reexported = [getattr(xtr_http_message_contracts, name) for name in factory.__all__]
    direct = [getattr(factory, name) for name in factory.__all__]

    assert reexported == direct
