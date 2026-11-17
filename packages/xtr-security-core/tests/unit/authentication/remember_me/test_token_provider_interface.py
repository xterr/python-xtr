"""The token provider keeps every persistent remember-me series."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_security_core.authentication.remember_me import (
    PersistentToken,
    TokenProviderInterface,
)

_LAST_USED = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
_ROTATED_USED = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)


class _MemoryTokenProvider:
    """A provider over a plain dict, standing in for the database."""

    def __init__(self) -> None:
        self._tokens: dict[str, PersistentToken] = {}

    async def load_token_by_series(self, series: str) -> PersistentToken:
        return self._tokens[series]

    async def delete_token_by_series(self, series: str) -> None:
        del self._tokens[series]

    async def update_token(
        self,
        series: str,
        expected_value: str,
        token_value: str,
        last_used: datetime,
    ) -> bool:
        token = self._tokens[series]
        if token.get_token_value() != expected_value:
            return False
        self._tokens[series] = PersistentToken(
            token.get_user_identifier(),
            series,
            token_value,
            last_used,
        )
        return True

    async def create_new_token(self, token: PersistentToken) -> None:
        self._tokens[token.get_series()] = token


def test_a_provider_satisfies_the_interface() -> None:
    assert isinstance(_MemoryTokenProvider(), TokenProviderInterface)


@pytest.mark.anyio
async def test_a_created_token_loads_by_its_series() -> None:
    provider = _MemoryTokenProvider()
    token = PersistentToken("alice", "series1", "value1", _LAST_USED)

    await provider.create_new_token(token)

    assert await provider.load_token_by_series("series1") is token


@pytest.mark.anyio
async def test_an_updated_token_rotates_its_value_and_last_use() -> None:
    provider = _MemoryTokenProvider()
    await provider.create_new_token(PersistentToken("alice", "series1", "value1", _LAST_USED))

    assert await provider.update_token("series1", "value1", "value2", _ROTATED_USED)

    rotated = await provider.load_token_by_series("series1")
    assert rotated.get_token_value() == "value2"
    assert rotated.get_last_used() is _ROTATED_USED


@pytest.mark.anyio
async def test_an_update_over_a_value_rotated_meanwhile_changes_nothing() -> None:
    provider = _MemoryTokenProvider()
    await provider.create_new_token(PersistentToken("alice", "series1", "value2", _LAST_USED))

    assert not await provider.update_token("series1", "value1", "value3", _ROTATED_USED)

    kept = await provider.load_token_by_series("series1")
    assert kept.get_token_value() == "value2"


@pytest.mark.anyio
async def test_a_deleted_series_loads_nothing() -> None:
    provider = _MemoryTokenProvider()
    await provider.create_new_token(PersistentToken("alice", "series1", "value1", _LAST_USED))

    await provider.delete_token_by_series("series1")

    with pytest.raises(KeyError):
        _ = await provider.load_token_by_series("series1")
