from __future__ import annotations

import pytest

from tests.support.smtp_auth_exchange import authenticate
from xtr_mailer.transport.smtp.auth import AuthenticatorInterface, LoginAuthenticator

pytestmark = pytest.mark.anyio


def test_it_is_the_login_mechanism() -> None:
    authenticator = LoginAuthenticator()

    assert isinstance(authenticator, AuthenticatorInterface)
    assert authenticator.get_auth_keyword() == "LOGIN"


async def test_it_answers_each_prompt_with_the_user_then_the_password() -> None:
    lines = await authenticate(LoginAuthenticator(), ["334 VXNlcm5hbWU6", "334 UGFzc3dvcmQ6"])

    assert lines == ["AUTH LOGIN", "dGVzdHVzZXI=", "cDRzc3cwcmQ="]
