"""The firewall map finds firewalls by name and by request matcher."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_http_foundation import ChainRequestMatcher, PathRequestMatcher
from xtr_security_core.exception import InvalidArgumentError

from tests.support.contexts import FakeFirewallContext
from tests.support.messages import make_message
from xtr_security_http.exception import UnknownFirewallError
from xtr_security_http.firewall_map import FirewallMap

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.firewall.exception_listener import ExceptionListener
    from xtr_security_http.firewall.firewall_listener_interface import (
        FirewallListenerInterface,
    )

pytestmark = pytest.mark.anyio


def _context(
    name: str,
    *,
    security: bool = True,
    listeners: tuple[FirewallListenerInterface, ...] = (),
    exception_listener: ExceptionListener | None = None,
    logout_listener: FirewallListenerInterface | None = None,
) -> FakeFirewallContext:
    return FakeFirewallContext(
        name=name,
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        security=security,
        listeners=listeners,
        exception_listener=exception_listener,
        logout_listener=logout_listener,
    )


@final
class _ChainMember:
    """A chain member whose hooks do nothing: the map only carries it."""

    __slots__ = ()

    async def supports(self, request: ServerRequestInterface) -> bool | None:
        del request
        return None

    async def authenticate(self, request_event: RequestEvent) -> None:
        del request_event

    @staticmethod
    def get_priority() -> int:
        return 0


def _anything() -> ChainRequestMatcher:
    return ChainRequestMatcher(())


def test_it_finds_a_firewall_by_name() -> None:
    context = _context("api")
    firewall_map = FirewallMap(((_anything(), context),))

    assert firewall_map.has("api") is True
    assert firewall_map.get("api") is context
    assert firewall_map.names() == ("api",)


def test_an_unknown_name_is_refused() -> None:
    firewall_map = FirewallMap(((_anything(), _context("api")),))

    with pytest.raises(UnknownFirewallError):
        _ = firewall_map.get("missing")


def test_duplicate_names_are_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = FirewallMap(
            (
                (_anything(), _context("api")),
                (_anything(), _context("api")),
            ),
        )


async def test_it_matches_the_first_firewall_that_claims_the_request() -> None:
    admin = _context("admin")
    api = _context("api")
    firewall_map = FirewallMap(
        (
            (PathRequestMatcher(r"^/admin"), admin),
            (PathRequestMatcher(r"^/api"), api),
        ),
    )

    message = make_message(path="/api/books")

    assert await firewall_map.match(message) is api


async def test_no_match_returns_none() -> None:
    firewall_map = FirewallMap(((PathRequestMatcher(r"^/api"), _context("api")),))
    message = make_message(path="/public")

    assert await firewall_map.match(message) is None


async def test_get_listeners_answers_the_matched_firewalls_chain_and_listeners() -> None:
    first, second = _ChainMember(), _ChainMember()
    exception_listener = cast("ExceptionListener", object())
    logout_listener = _ChainMember()
    api = _context(
        "api",
        listeners=(first, second),
        exception_listener=exception_listener,
        logout_listener=logout_listener,
    )
    firewall_map = FirewallMap(((PathRequestMatcher(r"^/api"), api),))

    answered = await firewall_map.get_listeners(make_message(path="/api/books"))

    assert answered == ((first, second), exception_listener, logout_listener)


async def test_get_listeners_for_an_unmatched_request_answers_an_empty_chain() -> None:
    firewall_map = FirewallMap(((PathRequestMatcher(r"^/api"), _context("api")),))

    answered = await firewall_map.get_listeners(make_message(path="/public"))

    assert answered == ((), None, None)
