"""The re-authentication interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_kernel.bridge import ResponseFactory

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.entry_point.re_authentication_entry_point_interface import (
    ReAuthenticationEntryPointInterface,
)

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface


@final
class _AskingAgain:
    """Starts a re-authentication, answering with a bare 401."""

    async def start_re_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> ResponseInterface:
        del request, token
        return ResponseFactory().create_response(401)


def test_a_re_authentication_entry_point_satisfies_the_interface() -> None:
    assert isinstance(_AskingAgain(), ReAuthenticationEntryPointInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), ReAuthenticationEntryPointInterface)


def test_an_access_token_authenticator_is_not_one_by_shape() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
        ResponseFactory(),
    )

    assert not isinstance(authenticator, ReAuthenticationEntryPointInterface)
