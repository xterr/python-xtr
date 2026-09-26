"""A source of services keyed by name, knowing which names it provides and their types.

A provider is its own contract, keyed by name; this package's
:class:`ContainerInterface` is a separate contract keyed by type and also
carries parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

__all__ = ["ServiceProviderInterface"]

T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class ServiceProviderInterface(Protocol[T_co]):
    """Provides a fixed set of services, each reachable by its name.

    Unlike a :class:`ContainerInterface`, which is keyed by type, a provider is
    keyed by name: it knows every name it can answer to, and the type each of
    those services has, without building any of them.

    ``runtime_checkable`` verifies method presence only, never signatures, so an
    implementation inherits this Protocol explicitly to have a type checker
    confirm it against the contract.
    """

    async def get(self, name: Hashable, /) -> T_co:
        """Return the service registered under ``name``, building it on first request.

        Raises:
            LookupError: If :meth:`has` is ``False`` for ``name``.
        """
        ...

    def has(self, name: Hashable, /) -> bool:
        """Whether a service is registered under ``name``."""
        ...

    def provided_services(self) -> Mapping[Hashable, type[object]]:
        """Return every provided name mapped to the type of the service it yields."""
        ...
