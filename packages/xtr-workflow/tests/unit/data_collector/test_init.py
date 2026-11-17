"""The package exports what it states."""

from __future__ import annotations

import xtr_workflow.data_collector


def test_exports_are_declared() -> None:
    package = xtr_workflow.data_collector
    missing = [name for name in package.__all__ if not hasattr(package, name)]

    assert type(package.__all__) is list
    assert missing == []
