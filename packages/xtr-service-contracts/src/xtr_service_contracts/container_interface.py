"""What a dependency-injection container answers to: building services and reading parameters.

Async, and keyed by type plus an optional qualifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Hashable

__all__ = ["ContainerInterface"]

T = TypeVar("T")


@runtime_checkable
class ContainerInterface(Protocol):
    """Builds and hands out services, and reads the parameters fixed while building.

    A service is identified by its type plus an optional ``qualifier`` that
    chooses between several services registered for that same type.

    ``runtime_checkable`` verifies method presence only, never signatures, so an
    implementation inherits this Protocol explicitly to have a type checker
    confirm it against the contract.
    """

    async def get(self, service: type[T], /, qualifier: Hashable | None = None) -> T:
        """Return the service of ``service`` type, the one named by ``qualifier`` if given.

        Raises:
            LookupError: If no such service is registered — that is, when
                :meth:`has` is ``False`` for the same arguments. A service that
                is registered but cannot be built raises its own error instead.
        """
        ...

    def has(self, service: type[object], /, qualifier: Hashable | None = None) -> bool:
        """Whether a service of ``service`` type (and ``qualifier``, if given) is registered."""
        ...

    def get_parameter(self, name: str, /) -> object:
        """Return the build-time parameter ``name``, a dotted path into nested configuration.

        Raises:
            LookupError: If :meth:`has_parameter` is ``False`` for ``name``.
        """
        ...

    def has_parameter(self, name: str, /) -> bool:
        """Whether the parameter ``name`` is set."""
        ...
