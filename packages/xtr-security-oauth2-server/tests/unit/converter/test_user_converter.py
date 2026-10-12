"""Turning a user the security family resolved into the one a token names."""

from __future__ import annotations

from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

from tests.support.users import SecurityUser
from xtr_security_oauth2_server.converter.user_converter import UserConverter
from xtr_security_oauth2_server.converter.user_converter_interface import UserConverterInterface


def test_it_declares_the_user_converter_contract() -> None:
    assert UserConverterInterface in UserConverter.__mro__


def test_it_keeps_only_the_identifier_the_protocol_writes_into_a_token() -> None:
    converted = UserConverter().to_entity(SecurityUser("user-1"))

    assert converted.get_identifier() == "user-1"


def test_what_it_answers_satisfies_the_user_contract() -> None:
    assert isinstance(UserConverter().to_entity(SecurityUser()), UserEntityInterface)


def test_it_drops_the_roles_the_firewall_reads() -> None:
    converted = UserConverter().to_entity(SecurityUser("user-1", ("ROLE_ADMIN",)))

    assert not hasattr(converted, "get_roles")
