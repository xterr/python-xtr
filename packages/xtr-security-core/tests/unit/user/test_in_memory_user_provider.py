"""The in-memory provider loads users from a set defined up front."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import (
    InvalidArgumentError,
    UnsupportedUserError,
    UserNotFoundError,
)
from xtr_security_core.user import InMemoryUser, InMemoryUserProvider, UserProviderInterface


def test_it_inherits_the_user_provider_interface() -> None:
    assert UserProviderInterface in InMemoryUserProvider.__mro__


@pytest.mark.anyio
async def test_loads_a_user_from_field_definitions() -> None:
    provider = InMemoryUserProvider(
        {"alice": {"password": "hash", "roles": ["ROLE_USER"], "enabled": True}},
    )

    user = await provider.load_user_by_identifier("alice")

    assert user.get_user_identifier() == "alice"
    assert user.get_roles() == ("ROLE_USER",)
    assert user.get_password() == "hash"


@pytest.mark.anyio
async def test_loads_a_ready_user() -> None:
    provider = InMemoryUserProvider({"alice": InMemoryUser("alice", roles=["ROLE_USER"])})

    user = await provider.load_user_by_identifier("alice")

    assert user.get_roles() == ("ROLE_USER",)


@pytest.mark.anyio
async def test_unknown_user_is_refused() -> None:
    provider = InMemoryUserProvider()

    with pytest.raises(UserNotFoundError):
        _ = await provider.load_user_by_identifier("nobody")


def test_supports_only_the_in_memory_user() -> None:
    provider = InMemoryUserProvider()

    assert provider.supports_class(InMemoryUser) is True
    assert provider.supports_class(str) is False


def test_a_ready_user_under_the_wrong_key_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = InMemoryUserProvider({"bob": InMemoryUser("alice")})


def test_a_non_string_password_is_refused() -> None:
    with pytest.raises(UnsupportedUserError):
        _ = InMemoryUserProvider({"alice": {"password": 123}})


def test_a_non_boolean_enabled_flag_is_refused() -> None:
    with pytest.raises(UnsupportedUserError):
        _ = InMemoryUserProvider({"alice": {"enabled": "yes"}})


def test_a_string_of_roles_is_refused() -> None:
    with pytest.raises(UnsupportedUserError):
        _ = InMemoryUserProvider({"alice": {"roles": "ROLE_USER"}})


@pytest.mark.anyio
async def test_add_user_extends_the_set() -> None:
    provider = InMemoryUserProvider()
    provider.add_user(InMemoryUser("late"))

    assert (await provider.load_user_by_identifier("late")).get_user_identifier() == "late"
