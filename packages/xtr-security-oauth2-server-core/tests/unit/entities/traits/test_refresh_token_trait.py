"""A refresh token names the access token it was issued beside, and its window."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.support.entities import AccessToken, RefreshToken

_EXPIRES_AT = datetime(2026, 4, 3, 5, 6, 7, tzinfo=UTC)


def test_it_hands_back_the_access_token_it_was_given() -> None:
    access_token = AccessToken()
    refresh_token = RefreshToken()
    refresh_token.set_access_token(access_token)

    assert refresh_token.get_access_token() is access_token


def test_reading_an_access_token_nobody_set_refuses() -> None:
    with pytest.raises(AttributeError):
        _ = RefreshToken().get_access_token()


def test_it_hands_back_the_expiry_it_was_given() -> None:
    refresh_token = RefreshToken()
    refresh_token.set_expiry_date_time(_EXPIRES_AT)

    assert refresh_token.get_expiry_date_time() == _EXPIRES_AT
