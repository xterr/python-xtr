"""A kernel that cannot compile: a service asks for something nothing registers."""

from __future__ import annotations

from typing import final

from xtr_dependency_injection import as_service

__all__ = ["Orphan", "Unregistered"]


class Unregistered:
    """Defined, scanned — and never registered: no ``@as_service``, no bundle defines it."""


@final
@as_service
class Orphan:
    """Asks for an unregistered type: building the container fails.

    The ``ContainerCompilationError`` names ``Orphan.missing`` and says how to register
    ``Unregistered``.
    """

    def __init__(self, missing: Unregistered) -> None:
        """Keep ``missing``."""
        self.missing = missing
