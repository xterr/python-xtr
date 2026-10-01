"""The null token stands for nobody authenticated."""

from __future__ import annotations

from xtr_security_core.authentication.token import NullToken
from xtr_security_core.authentication.token.token_interface import TokenInterface


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in NullToken.__mro__


def test_it_is_nobody() -> None:
    token = NullToken()

    assert token.get_user() is None
    assert token.get_user_identifier() == ""
    assert token.get_role_names() == ()
