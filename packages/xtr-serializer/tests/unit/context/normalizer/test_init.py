"""The normalizer context module exports its builders, and the package exports them too."""

from __future__ import annotations

import xtr_serializer
from xtr_serializer.context import normalizer


def test_every_exported_name_resolves() -> None:
    assert [name for name in normalizer.__all__ if not hasattr(normalizer, name)] == []


def test_the_package_exports_every_name_too() -> None:
    assert [name for name in normalizer.__all__ if name not in xtr_serializer.__all__] == []
