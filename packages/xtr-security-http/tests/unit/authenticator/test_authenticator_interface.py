"""The authenticator interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.header_access_token_extractor import HeaderAccessTokenExtractor
from xtr_security_http.authenticator.access_token_authenticator import AccessTokenAuthenticator
from xtr_security_http.authenticator.authenticator_interface import AuthenticatorInterface


def test_the_access_token_authenticator_satisfies_the_interface() -> None:
    authenticator = AccessTokenAuthenticator(
        FakeAccessTokenHandler({}),
        HeaderAccessTokenExtractor(),
    )

    assert isinstance(authenticator, AuthenticatorInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthenticatorInterface)
