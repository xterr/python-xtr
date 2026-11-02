from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.smtp_auth_exchange import authenticate
from xtr_mailer.transport.smtp.auth import AuthenticatorInterface

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp import EsmtpTransport

pytestmark = pytest.mark.anyio


class _TokenAuthenticator:
    """A mechanism of the application's own, written against the interface alone."""

    def get_auth_keyword(self) -> str:
        return "X-TOKEN"

    async def authenticate(self, client: EsmtpTransport) -> None:
        _ = await client.execute_command(f"AUTH X-TOKEN {client.get_password()}", [235])


def test_any_class_with_a_keyword_and_an_exchange_is_an_authenticator() -> None:
    assert isinstance(_TokenAuthenticator(), AuthenticatorInterface)
    assert not isinstance(object(), AuthenticatorInterface)


async def test_an_authenticator_of_its_own_drives_the_exchange() -> None:
    assert await authenticate(_TokenAuthenticator(), []) == ["AUTH X-TOKEN p4ssw0rd"]
