"""Consumers by the name of the source they answer for."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from ._built_consumers import BuiltConsumers, missing_consumer

if TYPE_CHECKING:
    from collections.abc import Hashable

    from .consumer_interface import ConsumerInterface

__all__ = ["ConsumerLocator"]


@final
class ConsumerLocator(ServiceProviderInterface["ConsumerInterface"]):
    """Hands over the consumer of a source, by the name the source is known under.

    Over consumers already built, or over a container's locator that builds
    each one — with its dependencies — when an event for it first arrives.
    The handler takes this rather than either, so where the consumers come
    from is the application's business and not the handler's.
    """

    __slots__ = ("_consumers",)

    def __init__(
        self,
        consumers: Mapping[str, ConsumerInterface] | ServiceProviderInterface[ConsumerInterface],
    ) -> None:
        """Hand over ``consumers``, by name."""
        self._consumers: ServiceProviderInterface[ConsumerInterface] = (
            BuiltConsumers(consumers) if isinstance(consumers, Mapping) else consumers
        )

    @override
    async def get(self, name: Hashable, /) -> ConsumerInterface:
        """Return the consumer of the source ``name``.

        Raises:
            LogicError: If there is none.
        """
        if not self._consumers.has(name):
            raise missing_consumer(name)
        return await self._consumers.get(name)

    @override
    def has(self, name: Hashable, /) -> bool:
        return self._consumers.has(name)

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return self._consumers.provided_services()
