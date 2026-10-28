"""The firewall listener services the wiring fixture registers, with priorities.

Three chain members — one ahead of the rest by priority, one ahead of a
neighbour by declared constraint — so a container test proves the bundle's
sorting pass orders the chain the firewall's configuration parks.
"""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_alias, as_service
from xtr_security_http.decorator.firewall_listener_order import FirewallListenerOrder
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall_listener_interface import (
    FirewallListenerInterface,
)

__all__ = [
    "AheadOfLateListener",
    "EarlyListener",
    "LateListener",
]


class _ChainListener(AbstractListener):
    """A chain member whose hooks do nothing: the ordering is what varies."""

    @override
    async def supports(self, request: object) -> bool | None:
        return None

    @override
    async def authenticate(self, request_event: object) -> None:
        return None


@final
@as_service
@as_alias(FirewallListenerInterface, qualifier="early")
class EarlyListener(_ChainListener):
    """The chain member that runs ahead of the rest, by priority."""

    __slots__ = ()

    @staticmethod
    @override
    def get_priority() -> int:
        return 256


@final
@as_service
@as_alias(FirewallListenerInterface, qualifier="late")
class LateListener(_ChainListener):
    """The chain member that runs last, at the default priority."""

    __slots__ = ()


@final
@as_service
@as_alias(FirewallListenerInterface, qualifier="ahead")
@FirewallListenerOrder(before=LateListener)
class AheadOfLateListener(_ChainListener):
    """The chain member that runs before its neighbour, by declared constraint."""

    __slots__ = ()
