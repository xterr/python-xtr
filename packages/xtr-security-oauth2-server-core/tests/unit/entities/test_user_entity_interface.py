"""The resource-owner contract is runtime-checkable."""

from __future__ import annotations

from tests.support.entities import make_user
from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface


def test_a_user_entity_satisfies_the_contract() -> None:
    user: UserEntityInterface = make_user()
    assert isinstance(user, UserEntityInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), UserEntityInterface)
