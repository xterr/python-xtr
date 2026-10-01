"""Custom credentials run a caller-supplied check, once."""

from __future__ import annotations

import pytest

from tests.support.users import accept, reject
from xtr_security_http.authenticator.passport.credentials.custom_credentials import (
    CustomCredentials,
)

pytestmark = pytest.mark.anyio


async def test_a_sync_check_verifies_and_resolves() -> None:
    credentials = CustomCredentials(accept, "ok")

    assert credentials.is_resolved() is False
    assert await credentials.verify(object()) is True
    assert credentials.is_resolved() is True


async def test_an_async_check_is_awaited() -> None:
    async def check(value: object, user: object) -> bool:
        del user
        return value == "ok"

    credentials = CustomCredentials(check, "ok")

    assert await credentials.verify(object()) is True


async def test_a_failing_check_resolves_but_returns_false() -> None:
    credentials = CustomCredentials(reject, "x")

    assert await credentials.verify(object()) is False
    assert credentials.is_resolved() is True


def test_the_credentials_are_readable() -> None:
    credentials = CustomCredentials(accept, "token")

    assert credentials.get_credentials() == "token"
