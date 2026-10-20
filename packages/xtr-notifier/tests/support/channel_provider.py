"""Channels by name behind the service provider contract, as a container's locator offers them."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_notifier.channel import ChannelInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

__all__ = ["ChannelProvider"]


@final
class ChannelProvider(ServiceProviderInterface[ChannelInterface]):
    """Hands out the channels it holds, recording each name it was asked to build."""

    def __init__(self, channels: Mapping[str, ChannelInterface]) -> None:
        self._channels = dict(channels)
        self.built: list[Hashable] = []

    @override
    async def get(self, name: Hashable, /) -> ChannelInterface:
        self.built.append(name)
        return self._channels[str(name)]

    @override
    def has(self, name: Hashable, /) -> bool:
        return name in self._channels

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType(dict.fromkeys(self._channels, ChannelInterface))
