"""The shipped access-token model satisfies the contract a manager stores it through."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.access_token import AccessToken
from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface
from xtr_security_oauth2_server.model.client import Client


def test_the_shipped_model_satisfies_it() -> None:
    token = AccessToken(
        "at-1",
        datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC),
        Client("C", "client-1", None),
        None,
        (),
    )

    assert isinstance(token, AccessTokenInterface)
