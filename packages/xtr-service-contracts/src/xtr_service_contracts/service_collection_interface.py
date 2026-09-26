"""A service provider that is also countable and iterable over its ``(name, service)`` pairs.

Iteration is asynchronous, because building a service is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar, runtime_checkable

from .service_provider_interface import ServiceProviderInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Hashable

__all__ = ["ServiceCollectionInterface"]

T_co = TypeVar("T_co", covariant=True)


@runtime_checkable
class ServiceCollectionInterface(ServiceProviderInterface[T_co], Protocol[T_co]):
    """A :class:`ServiceProviderInterface` that also reports its size and iterates.

    Iterating yields ``(name, service)`` pairs, each service built lazily as it
    is reached, in the order :meth:`~ServiceProviderInterface.provided_services`
    lists them.

    ``runtime_checkable`` verifies method presence only, never signatures, so an
    implementation inherits this Protocol explicitly to have a type checker
    confirm it against the contract.
    """

    def __len__(self) -> int:
        """Return how many services this collection provides."""
        ...

    def __aiter__(self) -> AsyncIterator[tuple[Hashable, T_co]]:
        """Iterate over ``(name, service)`` pairs, building each service as it is reached."""
        ...
