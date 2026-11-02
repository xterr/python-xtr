from __future__ import annotations

import pytest

from tests.unit.transport.smtp.auth.exchange import authenticate
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.transport.smtp.auth import AuthenticatorInterface, PlainAuthenticator

pytestmark = pytest.mark.anyio


def test_it_is_the_plain_mechanism() -> None:
    authenticator = PlainAuthenticator()

    assert isinstance(authenticator, AuthenticatorInterface)
    assert authenticator.get_auth_keyword() == "PLAIN"


async def test_it_sends_the_user_twice_and_the_password_in_one_line() -> None:
    assert await authenticate(PlainAuthenticator(), []) == [
        "AUTH PLAIN dGVzdHVzZXIAdGVzdHVzZXIAcDRzc3cwcmQ="
    ]


async def test_a_password_utf8_cannot_write_is_refused_without_quoting_it() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = await authenticate(PlainAuthenticator(), [], password="p\udcff")

    assert str(caught.value) == "The SMTP credentials must only hold characters UTF-8 can write."
