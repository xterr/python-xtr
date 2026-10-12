"""The authorization-request contract is runtime-checkable."""

from __future__ import annotations

from xtr_security_oauth2_server.request_types.authorization_request import AuthorizationRequest
from xtr_security_oauth2_server.request_types.authorization_request_interface import (
    AuthorizationRequestInterface,
)


def test_the_shipped_request_satisfies_the_contract() -> None:
    request: AuthorizationRequestInterface = AuthorizationRequest()
    assert isinstance(request, AuthorizationRequestInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AuthorizationRequestInterface)
