"""The base of every startup check, with a class-level ``@autoconfigure`` rule.

Each check is its own key — ``(CatalogCheck, None)`` and so on — so ``before``/``after``
can name the others by type. The kernel's emission order, which ``debug:container`` prints
and :func:`bookshop.service.run_startup_checks.run_startup_checks` follows, becomes:

1. ``ConfigurationCheck`` — priority 10;
2. ``CatalogCheck`` — no priority, ``before=[SearchIndexCheck]``;
3. ``SearchIndexCheck`` — priority 0;
4. ``MessengerCheck`` — no priority, ``after=[SearchIndexCheck]``.

The scan finds them in another order — by module name: the order comes from the constraints,
not from the source. A contradiction (``before`` a lower priority) is a ``ServiceOrderError``.
"""

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
# ``bookshop.service.request_scoped`` and ``bookshop.service.exporter``).
@autoconfigure(tags=[(STARTUP_CHECK_TAG, _describe), "bookshop.health"])
class StartupCheck(ABC):
    """Something verified once the kernel boots; a failing check fails the boot."""

    @abstractmethod
    async def run(self) -> str:
        """Verify, and describe what was verified.

        Raises:
            RuntimeError: When the check fails.
        """
