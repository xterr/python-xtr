"""Consumers a test can look at afterwards, and a provider handing them over."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_remote_event import ConsumerInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from xtr_remote_event import RemoteEvent

__all__ = ["ConsumerProvider", "NotAConsumer", "RecordingConsumer"]


@final
class RecordingConsumer:
    """Keeps every event it was handed, so a test can say which one arrived."""

    def __init__(self) -> None:
        self.consumed: list[RemoteEvent] = []

    async def consume(self, event: RemoteEvent) -> None:
        self.consumed.append(event)


@final
class NotAConsumer:
    """Registered under a name, but taking events under one the contract does not name."""

    async def handle(self, event: RemoteEvent) -> None:
        del event


@final
class ConsumerProvider(ServiceProviderInterface[ConsumerInterface]):
    """Hands over what was registered by name — what a container's locator does, without one.

    Registration takes any object, and ``get`` promises a consumer, because
    that is the gap a container leaves too: it is told which class answers for
    a name and builds it, with nothing checking the class consumes anything.
    """

    def __init__(self, registered: Mapping[str, object]) -> None:
        self._registered = dict(registered)

    @override
    async def get(self, name: Hashable, /) -> ConsumerInterface:
        return cast("ConsumerInterface", self._registered[str(name)])

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._registered

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType({name: type(r) for name, r in self._registered.items()})
