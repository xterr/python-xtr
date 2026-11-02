"""The authentication helper logs in with one authenticator and reports what the server read."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.smtp_auth_exchange import authenticate

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp import EsmtpTransport

pytestmark = pytest.mark.anyio


class _TwoLineAuthenticator:
    def get_auth_keyword(self) -> str:
        return "X-TWO"

    async def authenticate(self, client: EsmtpTransport) -> None:
        _ = await client.execute_command("AUTH X-TWO", [334])
        _ = await client.execute_command(client.get_password(), [235])


async def test_it_returns_the_exchange_lines_the_server_read() -> None:
    lines = await authenticate(_TwoLineAuthenticator(), ["334 go on"])

    assert lines == ["AUTH X-TWO", "p4ssw0rd"]


async def test_it_logs_in_with_the_password_given() -> None:
    lines = await authenticate(_TwoLineAuthenticator(), ["334 go on"], password="other")

    assert lines == ["AUTH X-TWO", "other"]
