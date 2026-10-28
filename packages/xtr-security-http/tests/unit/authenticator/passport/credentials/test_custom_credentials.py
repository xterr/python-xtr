"""Custom credentials run a caller-supplied check, resolving only on success."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import BadCredentialsError

from tests.support.users import accept, reject
from xtr_security_http.authenticator.passport.credentials.custom_credentials import (
    CustomCredentials,
)

pytestmark = pytest.mark.anyio


async def test_a_sync_check_verifies_and_resolves() -> None:
    credentials = CustomCredentials(accept, "ok")

    assert credentials.is_resolved() is False
    await credentials.execute_custom_checker(object())
    assert credentials.is_resolved() is True


async def test_an_async_check_is_awaited() -> None:
    async def check(value: object, user: object) -> bool:
        del user
        return value == "ok"

    credentials = CustomCredentials(check, "ok")

    await credentials.execute_custom_checker(object())

    assert credentials.is_resolved() is True


async def test_a_failing_check_raises_and_stays_unresolved() -> None:
    credentials = CustomCredentials(reject, "x")

    with pytest.raises(BadCredentialsError):
        await credentials.execute_custom_checker(object())

    assert credentials.is_resolved() is False


async def test_a_truthy_but_not_true_result_fails() -> None:
    # A checker returning a truthy non-True value is refused: only a strictly
    # True result verifies.
    def truthy(value: object, user: object) -> object:
        del value, user
        return "yes"

    credentials = CustomCredentials(truthy, "x")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # deliberately returns a non-bool

    with pytest.raises(BadCredentialsError):
        await credentials.execute_custom_checker(object())


def test_the_credentials_are_readable() -> None:
    credentials = CustomCredentials(accept, "token")

    assert credentials.get_credentials() == "token"
