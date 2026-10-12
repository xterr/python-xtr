"""The stand-in user satisfies the security family's own user contract."""

from __future__ import annotations

from xtr_security_core.user.user_interface import UserInterface

from tests.support.users import SecurityUser


def test_it_satisfies_the_user_contract() -> None:
    assert isinstance(SecurityUser(), UserInterface)


def test_it_reports_the_identifier_it_was_given() -> None:
    assert SecurityUser("someone").get_user_identifier() == "someone"


def test_it_reports_the_roles_it_was_given() -> None:
    assert SecurityUser(roles=("ROLE_ADMIN",)).get_roles() == ("ROLE_ADMIN",)
