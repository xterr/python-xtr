"""The shipped code model satisfies the contract a manager stores it through."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_oauth2_server.model.authorization_code import AuthorizationCode
from xtr_security_oauth2_server.model.authorization_code_interface import (
    AuthorizationCodeInterface,
)
from xtr_security_oauth2_server.model.client import Client


def test_the_shipped_model_satisfies_it() -> None:
    code = AuthorizationCode(
        "ac-1",
        datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC),
        Client("C", "client-1", None),
        None,
        (),
    )

    assert isinstance(code, AuthorizationCodeInterface)
