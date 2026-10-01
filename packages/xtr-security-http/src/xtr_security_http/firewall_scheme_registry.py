"""The OpenAPI scheme each firewall contributes, and the holder a scheme reads it through."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi.openapi.models import SecurityBase as SecurityBaseModel

__all__ = [
    "FirewallSchemeRegistry",
    "active_firewall_scheme_registry",
    "active_firewall_schemes",
]


@final
@dataclass(frozen=True, slots=True)
class _SchemeEntry:
    """The OpenAPI model and name one firewall contributes."""

    model: SecurityBaseModel
    scheme_name: str


@final
class FirewallSchemeRegistry:
    """The OpenAPI scheme each firewall contributes, filled once when the kernel boots.

    The generated schema is built synchronously, inside the request serving
    ``/openapi.json``, where an ``await`` on the container is not possible. So
    each firewall's model and name are resolved once at boot and kept here for
    that synchronous read. The bundle fills one of these per kernel and makes
    it the active registry for the requests that kernel serves; a test fills
    one and activates it with :func:`active_firewall_schemes`.
    """

    __slots__ = ("_schemes",)

    def __init__(self) -> None:
        """Start with no firewall schemes registered."""
        self._schemes: dict[str, _SchemeEntry] = {}

    def register(self, name: str, model: SecurityBaseModel, scheme_name: str | None = None) -> None:
        """Record the OpenAPI ``model`` and name the firewall ``name`` shows."""
        self._schemes[name] = _SchemeEntry(model, scheme_name or name)

    def get(self, name: str) -> _SchemeEntry | None:
        """Return the scheme registered for ``name``, or ``None`` when there is none."""
        return self._schemes.get(name)

    def names(self) -> tuple[str, ...]:
        """Return the names of every firewall with a registered scheme."""
        return tuple(self._schemes)


# The OpenAPI scheme is read synchronously while the schema is generated, from
# a context the reader does not share with whoever activated the registry (a
# fixture, an async generator). A plain module-level holder — restored on exit
# — is read the same from any context; the Phase 5 bundle keys it per kernel so
# concurrent kernels stay isolated.
_ACTIVE: list[FirewallSchemeRegistry | None] = [None]


@contextmanager
def active_firewall_schemes(registry: FirewallSchemeRegistry) -> Generator[None, None, None]:
    """Make ``registry`` the one a firewall scheme reads while the block is entered.

    The bundle activates a kernel's registry for the span its requests are
    served; a test activates one around the block it serves an application in.
    The previous registry is restored on exit.
    """
    previous = _ACTIVE[0]
    _ACTIVE[0] = registry
    try:
        yield
    finally:
        _ACTIVE[0] = previous


def active_firewall_scheme_registry() -> FirewallSchemeRegistry | None:
    """Return the registry a firewall scheme reads now, or ``None`` when none is active."""
    return _ACTIVE[0]
