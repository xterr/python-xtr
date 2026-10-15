"""The persistent token is one remember-me series entry."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_security_core.authentication.remember_me import PersistentToken
from xtr_security_core.exception import InvalidArgumentError

_LAST_USED = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_it_carries_its_fields() -> None:
    token = PersistentToken("alice", "series1", "value1", _LAST_USED)

    assert token.get_user_identifier() == "alice"
    assert token.get_series() == "series1"
    assert token.get_token_value() == "value1"
    assert token.get_last_used() is _LAST_USED


def test_an_empty_user_identifier_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="user_identifier"):
        _ = PersistentToken("", "series1", "value1", _LAST_USED)


def test_an_empty_series_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="series"):
        _ = PersistentToken("alice", "", "value1", _LAST_USED)


def test_an_empty_token_value_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="token_value"):
        _ = PersistentToken("alice", "series1", "", _LAST_USED)
