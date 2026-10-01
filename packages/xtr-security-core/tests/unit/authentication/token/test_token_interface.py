"""The token interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authentication.token import AbstractToken, NullToken, UsernamePasswordToken
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.user import InMemoryUser


def test_every_token_satisfies_the_interface() -> None:
    tokens = (
        AbstractToken(),
        NullToken(),
        UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]),
    )
    for token in tokens:
        assert isinstance(token, TokenInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), TokenInterface)
