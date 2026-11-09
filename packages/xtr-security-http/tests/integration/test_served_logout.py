"""A logout served the way a browser submits one: its forgery token posted in a form.

The request goes through the kernel's lifecycle middleware, so the chain is
handed the request the kernel serves — connected to its wire, the body unread
— and the real logout step reads the proof out of the posted form before it
logs the request out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

import pytest
from starlette.applications import Starlette
from xtr_event_dispatcher import EventDispatcher
from xtr_http_foundation import PathRequestMatcher
from xtr_http_kernel import RequestLifecycleMiddleware
from xtr_http_kernel.bridge import ResponseFactory, StarletteHttpFactory
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_csrf.csrf_token import CsrfToken

from tests.support.contexts import FakeFirewallContext
from tests.support.served import message_factory, send
from xtr_security_http.event_listener.default_logout_listener import DefaultLogoutListener
from xtr_security_http.firewall.firewall import Firewall
from xtr_security_http.firewall.logout_listener import LogoutListener
from xtr_security_http.firewall_map import FirewallMap
from xtr_security_http.http_utils import HttpUtils

if TYPE_CHECKING:
    from starlette.types import ASGIApp

pytestmark = pytest.mark.anyio

_FORM = "application/x-www-form-urlencoded"

#: The one forgery token value the fixture's manager vouches for.
_MINTED: Final = "minted"


@final
class _MintedOnly:
    """A forgery-token manager vouching for the one value it mints."""

    async def get_token(self, token_id: str) -> CsrfToken:
        return CsrfToken(token_id, _MINTED)

    async def refresh_token(self, token_id: str) -> CsrfToken:
        return CsrfToken(token_id, _MINTED)

    async def remove_token(self, token_id: str) -> str | None:
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        return token.get_value() == _MINTED


def _application() -> ASGIApp:
    """Return an application whose one firewall logs out, asking for a forgery token."""
    http_utils = HttpUtils(ResponseFactory())
    logout_dispatcher = EventDispatcher()
    logout_dispatcher.add_subscriber(DefaultLogoutListener(http_utils, "/bye"))
    logout = LogoutListener(
        TokenStorage(),
        http_utils,
        logout_dispatcher,
        StarletteHttpFactory(),
        _MintedOnly(),
    )
    firewall_map = FirewallMap(
        [
            (
                PathRequestMatcher("^/"),
                FakeFirewallContext(
                    name="main",
                    authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] -- the chain never asks the context for it
                    access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] -- the chain never asks the context for it
                    logout_listener=logout,
                ),
            ),
        ],
    )
    dispatcher = EventDispatcher()
    dispatcher.add_subscriber(Firewall(firewall_map))
    return RequestLifecycleMiddleware(
        Starlette(), dispatcher=dispatcher, message_factory=message_factory()
    )


async def test_a_logout_whose_forgery_token_is_posted_in_a_form_is_accepted() -> None:
    status, headers, _content = await send(
        _application(),
        "POST",
        "/logout",
        f"_csrf_token={_MINTED}".encode(),
        content_type=_FORM,
    )

    assert status == 302
    assert headers["location"] == "/bye"
