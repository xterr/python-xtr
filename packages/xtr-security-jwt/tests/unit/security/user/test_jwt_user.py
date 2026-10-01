"""The stateless user is built from a token's claims and reports its roles."""

from __future__ import annotations

from xtr_security_core.user.user_interface import UserInterface

from xtr_security_jwt.security.user.jwt_user import JwtUser
from xtr_security_jwt.security.user.jwt_user_interface import JwtUserInterface


def test_it_implements_the_user_interfaces() -> None:
    assert UserInterface in JwtUser.__mro__
    assert JwtUserInterface in JwtUser.__mro__


def test_it_reports_its_identifier_and_roles() -> None:
    user = JwtUser("ada", ("ROLE_USER", "ROLE_ADMIN"))

    assert user.get_user_identifier() == "ada"
    assert list(user.get_roles()) == ["ROLE_USER", "ROLE_ADMIN"]


def test_create_from_payload_reads_the_roles_claim() -> None:
    user = JwtUser.create_from_payload("ada", {"roles": ["ROLE_USER"]})

    assert user.get_user_identifier() == "ada"
    assert list(user.get_roles()) == ["ROLE_USER"]


def test_create_from_payload_without_roles_yields_none() -> None:
    user = JwtUser.create_from_payload("ada", {})

    assert list(user.get_roles()) == []


def test_create_from_payload_ignores_a_non_list_roles_claim() -> None:
    user = JwtUser.create_from_payload("ada", {"roles": "ROLE_USER"})

    assert list(user.get_roles()) == []


def test_it_stringifies_to_its_identifier() -> None:
    assert str(JwtUser("ada")) == "ada"
