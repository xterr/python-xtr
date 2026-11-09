"""A user switch served the way a browser submits one: the user to become posted in a form.

The request goes through the kernel's lifecycle middleware, so the chain is
handed the request the kernel serves — connected to its wire, the body unread
— and the real switch step reads the user to become out of the posted form,
the only place the request names them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from starlette.applications import Starlette
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.switch_user_token import SwitchUserToken
from xtr_security_core.user import InMemoryUser

from tests.support.contexts import FakeFirewallContext
from tests.support.served import message_factory, send
from xtr_security_http.authenticator.token.post_authentication_token import (
    PostAuthenticationToken,
)
from xtr_security_http.firewall.abstract_listener import AbstractListener
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall.switch_user_listener import SwitchUserListener
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.http_utils import HttpUtils

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.types import ASGIApp
    from xtr_http_kernel import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.access_decision import AccessDecision
    from xtr_security_core.user.user_interface import UserInterface

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"


@final
class _Users:
    """Hands back a user for any identifier."""

    async def load_user_by_identifier(self, identifier: str) -> UserInterface:
        return InMemoryUser(identifier, roles=("ROLE_USER",))

    async def refresh_user(self, user: UserInterface) -> UserInterface:
        return user

    def supports_class(self, user_class: type) -> bool:
        del user_class
        return True


@final
class _Granting:
    """Grants every switch it is asked to decide."""

    async def decide(
        self,
        token: TokenInterface,
        attributes: Sequence[object],
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        del token, attributes, subject, access_decision
        return True


@final
class _Checker:
    """Clears every account it is asked to check."""

    async def check_pre_auth(self, user: UserInterface) -> None:
        del user

    async def check_post_auth(
        self,
        user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        del user, token


@final
class _SignedIn(AbstractListener):
    """Holds the caller as the admin, the way the context step restores a session."""

    def __init__(self, storage: TokenStorage) -> None:
        self._storage = storage

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        return True

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        self._storage.set_token(PostAuthenticationToken(InMemoryUser("admin"), "main", ()))


def _application(storage: TokenStorage) -> ASGIApp:
    """Return an application whose one firewall lets its signed-in caller switch."""
    switch = SwitchUserListener(
        storage,
        _Users(),
        _Checker(),
        "main",
        _Granting(),
        StarletteHttpFactory(),
        HttpUtils(ResponseFactory()),
    )
    firewall_map = FirewallMap(
        [
            (
                PathRequestMatcher("^/"),
                FakeFirewallContext(
                    name="main",
                    authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] -- the chain never asks the context for it
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] -- the chain never asks the context for it
                    listeners=(_SignedIn(storage), switch),
                ),
            ),
        ],
    )
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(Firewall(firewall_map))
    return RequestLifecycleMiddleware(
        Starlette(), dispatcher=dispatcher, message_factory=message_factory()
    )


async def test_a_switch_posted_in_a_form_switches_the_user() -> None:
    storage = TokenStorage()

    status, headers, _content = await send(
        _application(storage), "POST", "/orders", b"_switch_user=ada", content_type=_FORM
    )

    assert (status, headers["location"]) == (302, "https://example.com/orders")
    switched = storage.get_token()
    assert isinstance(switched, SwitchUserToken)
    assert switched.get_user_identifier() == "ada"
