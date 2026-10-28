"""Locks: file locks by default, and an in-process resource for stock.

``default`` is provided without a qualifier — the schedule's lock comes from it, so two
worker processes on one machine never both send a run. ``stock`` keeps its locks in memory:
they only have to keep two orders of one process from interleaving.
"""

from __future__ import annotations

from xtr_dependency_injection import configure
from xtr_lock.bundle import LockConfig

__all__ = ["lock"]


@configure
def lock() -> LockConfig:
    """Two resources: ``default`` in files, ``stock`` in memory."""
    return LockConfig(resources={"default": "flock", "stock": "in-memory"})
