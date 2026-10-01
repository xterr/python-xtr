"""The JWT-user interface is runtime-checkable against the stateless user."""

from __future__ import annotations

from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_interface import JwtUserInterface


def test_the_stateless_user_is_an_instance() -> None:
    assert isinstance(JwtUser("ada"), JwtUserInterface)


def test_a_user_built_from_a_payload_is_an_instance() -> None:
    user = JwtUser.create_from_payload("ada", {"roles": ["ROLE_USER"]})

    assert isinstance(user, JwtUserInterface)
    assert user.get_user_identifier() == "ada"
