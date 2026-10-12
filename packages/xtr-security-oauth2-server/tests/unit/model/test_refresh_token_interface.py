"""The shipped refresh-token model satisfies the contract a manager stores it through."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.refresh_token import RefreshToken
from xtr_security_oauth2_server.model.refresh_token_interface import RefreshTokenInterface


def test_the_shipped_model_satisfies_it() -> None:
    token = RefreshToken("rt-1", datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC), None)

    assert isinstance(token, RefreshTokenInterface)
