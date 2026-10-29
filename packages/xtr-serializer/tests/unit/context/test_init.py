"""The context module exports the context type and its builders, and the package does too."""

from __future__ import annotations

import xtr_serializer
from xtr_serializer import context


def test_every_exported_name_resolves() -> None:
    assert [name for name in context.__all__ if not hasattr(context, name)] == []


def test_the_package_exports_every_name_too() -> None:
    assert [name for name in context.__all__ if name not in xtr_serializer.__all__] == []
