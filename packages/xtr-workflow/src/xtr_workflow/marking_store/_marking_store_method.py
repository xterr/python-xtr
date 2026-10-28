"""How the method marking store reaches a subject's marking."""

from __future__ import annotations

from enum import Enum

__all__ = ["MarkingStoreMethod"]


class MarkingStoreMethod(Enum):
    """How the method marking store reaches the marking of a class of subjects.

    Worked out once per class, separately for reading and for writing: a
    subject may have a getter and no setter, and be written through its
    attribute.
    """

    METHOD = "method"
    """Through the subject's accessor: ``get_<property>()`` or ``set_<property>()``."""

    PROPERTY = "property"
    """Through the subject's attribute ``<property>`` itself."""
