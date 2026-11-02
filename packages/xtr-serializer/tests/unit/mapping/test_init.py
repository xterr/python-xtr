"""The mapping module exports its mapping, and the package exports it too."""

from __future__ import annotations

import xtr_serializer
from xtr_serializer import mapping


def test_every_exported_name_resolves() -> None:
    assert [name for name in mapping.__all__ if not hasattr(mapping, name)] == []


def test_the_package_exports_every_name_too() -> None:
    assert [name for name in mapping.__all__ if name not in xtr_serializer.__all__] == []
