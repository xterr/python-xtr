"""The base of every startup check, with a class-level ``@autoconfigure`` rule."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Final

from xtr_dependency_injection import autoconfigure

__all__ = ["STARTUP_CHECK_TAG", "StartupCheck"]

STARTUP_CHECK_TAG: Final = "bookshop.startup_check"


def _describe(check: type) -> Mapping[str, object]:
    """Compute the tag's attributes from the concrete class the rule matched."""
    return {"check": check.__name__, "module": check.__module__}


# ``@autoconfigure`` on a base class: every registered subclass gets the tag. A tag entry is a
# bare name or ``(name, attributes)``; ``attributes`` may be a callable, called once per
# concrete class. ``lifetime=`` and ``factory=`` are the other two options (see
# ``bookshop.ordering.request_scoped`` and ``bookshop.reporting.exporters``).
@autoconfigure(tags=[(STARTUP_CHECK_TAG, _describe), "bookshop.health"])
class StartupCheck(ABC):
    """Something verified once the kernel boots; a failing check fails the boot."""

    @abstractmethod
    async def run(self) -> str:
        """Verify, and describe what was verified.

        Raises:
            RuntimeError: When the check fails.
        """
