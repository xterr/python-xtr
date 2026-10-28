"""The package states what it exports, and exports what it states."""

from __future__ import annotations

import xtr_workflow


def test_exports_are_declared() -> None:
    missing = [name for name in xtr_workflow.__all__ if not hasattr(xtr_workflow, name)]

    assert type(xtr_workflow.__all__) is list
    assert missing == []
