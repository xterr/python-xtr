"""The resource owner a grant writes into a token, reduced to an identifier."""

from __future__ import annotations

from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

from xtr_security_oauth2_server.entity.user import User


def test_it_satisfies_the_user_contract() -> None:
    assert UserEntityInterface in User.__mro__
    user = User()
    user.set_identifier("user-1")

    assert isinstance(user, UserEntityInterface)


def test_it_reports_the_identifier_it_was_given() -> None:
    user = User()
    user.set_identifier("user-1")

    assert user.get_identifier() == "user-1"
