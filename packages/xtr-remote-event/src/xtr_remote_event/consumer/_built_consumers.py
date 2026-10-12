"""Consumers already built, handed over by name."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_remote_event.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from .consumer_interface import ConsumerInterface

__all__ = ["BuiltConsumers", "missing_consumer"]


def missing_consumer(name: Hashable) -> LogicError:
    """Return the error for an event of ``name`` that nothing is registered to consume.

    One sentence, written once, because both ways of reaching a consumer end
    at it: a mapping that never had the name, and a container's locator that
    was never told about it. A consumer arriving under one name and being
    asked for under another is the same mistake either way.
    """
    return LogicError(f'Unable to find a consumer for message of type "{name}".')


@final
class BuiltConsumers(ServiceProviderInterface["ConsumerInterface"]):
    """Hands over consumers from a mapping — the locator for code with no container."""

    __slots__ = ("_consumers",)

    def __init__(self, consumers: Mapping[str, ConsumerInterface]) -> None:
        """Hand over ``consumers``, by name.

        The mapping is copied: what it holds is fixed once a locator is built,
        so a caller still writing to its own dict cannot change who answers
        for a source halfway through a worker's run.
        """
        self._consumers = dict(consumers)

    @override
    async def get(self, name: Hashable, /) -> ConsumerInterface:
        """Return the consumer registered under ``name``.

        Raises:
            LogicError: If there is none.
        """
        consumer = self._consumers.get(str(name))
        if consumer is None:
            raise missing_consumer(name)
        return consumer

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._consumers

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType({name: type(c) for name, c in self._consumers.items()})
