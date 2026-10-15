"""The token verifier has an extra say over a persistent token's value."""

from __future__ import annotations

import hmac
from datetime import UTC, datetime

import pytest

from xtr_security_core.authentication.remember_me import (
    PersistentToken,
    TokenVerifierInterface,
)

_LAST_USED = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_ROTATED_USED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


class _ExactTokenVerifier:
    """The plain verifier: a value counts only when it is the current one."""

    def __init__(self) -> None:
        self.updates: list[tuple[str, str, datetime]] = []

    async def verify_token(self, token: PersistentToken, token_value: str) -> bool:
        return hmac.compare_digest(token.get_token_value(), token_value)

    async def update_existing_token(
        self,
        token: PersistentToken,
        token_value: str,
        last_used: datetime,
    ) -> None:
        self.updates.append((token.get_series(), token_value, last_used))


def _token() -> PersistentToken:
    return PersistentToken("alice", "series1", "value1", _LAST_USED)


def test_a_verifier_satisfies_the_interface() -> None:
    assert isinstance(_ExactTokenVerifier(), TokenVerifierInterface)


@pytest.mark.anyio
async def test_the_current_value_verifies() -> None:
    assert await _ExactTokenVerifier().verify_token(_token(), "value1") is True


@pytest.mark.anyio
async def test_another_value_does_not_verify() -> None:
    assert await _ExactTokenVerifier().verify_token(_token(), "value2") is False


@pytest.mark.anyio
async def test_an_update_is_recorded_on_the_token() -> None:
    verifier = _ExactTokenVerifier()

    await verifier.update_existing_token(_token(), "value2", _ROTATED_USED)

    assert verifier.updates == [("series1", "value2", _ROTATED_USED)]
