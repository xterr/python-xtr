"""The access-token handler interface is a runtime-checkable protocol."""

from __future__ import annotations

from tests.support.http import FakeAccessTokenHandler
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)


def test_a_conforming_handler_satisfies_the_interface() -> None:
    assert isinstance(FakeAccessTokenHandler({}), AccessTokenHandlerInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AccessTokenHandlerInterface)
