from __future__ import annotations

import pytest

from tests.support.smtp_auth_exchange import authenticate
from xtr_mailer.transport.smtp.auth import AuthenticatorInterface, XOAuth2Authenticator

pytestmark = pytest.mark.anyio


def test_it_is_the_xoauth2_mechanism() -> None:
    authenticator = XOAuth2Authenticator()

    assert isinstance(authenticator, AuthenticatorInterface)
    assert authenticator.get_auth_keyword() == "XOAUTH2"


async def test_it_sends_the_user_and_the_password_as_a_bearer_token() -> None:
    assert await authenticate(XOAuth2Authenticator(), []) == [
        "AUTH XOAUTH2 dXNlcj10ZXN0dXNlcgFhdXRoPUJlYXJlciBwNHNzdzByZAEB"
    ]
