"""The listener template: the chain's default priority, and nothing decided for the subclass."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall_listener_interface import FirewallListenerInterface

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface


def test_the_default_priority_is_zero() -> None:
    assert AbstractListener.get_priority() == 0


def test_a_subclass_keeps_the_default_priority_until_it_overrides_it() -> None:
    class StayingListener(AbstractListener):
        @override
        async def supports(self, request: ServerRequestInterface) -> bool | None:
            return None

        @override
        async def authenticate(self, request_event: RequestEvent) -> None:
            return None

    @final
    class MovingListener(StayingListener):
        @staticmethod
        @override
        def get_priority() -> int:
            return -255

    assert StayingListener.get_priority() == 0
    assert MovingListener.get_priority() == -255


def test_a_subclass_satisfies_the_listener_interface() -> None:
    @final
    class ConcreteListener(AbstractListener):
        @override
        async def supports(self, request: ServerRequestInterface) -> bool | None:
            return None

        @override
        async def authenticate(self, request_event: RequestEvent) -> None:
            return None

    assert isinstance(ConcreteListener(), FirewallListenerInterface)
