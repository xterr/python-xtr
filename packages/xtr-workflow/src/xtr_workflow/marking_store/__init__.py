"""Where a workflow keeps each subject's marking between transitions."""

from __future__ import annotations

from .marking_store_interface import MarkingStoreInterface
from .method_marking_store import MethodMarkingStore

__all__ = ["MarkingStoreInterface", "MethodMarkingStore"]
