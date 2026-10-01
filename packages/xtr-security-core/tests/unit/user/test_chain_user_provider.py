"""The chain provider tries each provider in turn."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_security_core.exception import UnsupportedUserError, UserNotFoundError
from xtr_security_core.user import (
    AttributesBasedUserProviderInterface,
    ChainUserProvider,
    InMemoryUser,
    InMemoryUserProvider,
    PasswordUpgraderInterface,
    UserProviderInterface,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user import PasswordAuthenticatedUserInterface, UserInterface


def test_it_inherits_its_interfaces() -> None:
    for interface in (
        AttributesBasedUserProviderInterface,
        UserProviderInterface,
        PasswordUpgraderInterface,
    ):
        assert interface in ChainUserProvider.__mro__


@pytest.mark.anyio
async def test_loads_from_the_first_provider_that_has_the_user() -> None:
    first = InMemoryUserProvider({"alice": InMemoryUser("alice", roles=["ROLE_A"])})
    second = InMemoryUserProvider({"bob": InMemoryUser("bob", roles=["ROLE_B"])})
    chain = ChainUserProvider([first, second])

    assert (await chain.load_user_by_identifier("bob")).get_roles() == ("ROLE_B",)


@pytest.mark.anyio
async def test_unknown_user_is_refused_when_none_have_it() -> None:
    chain = ChainUserProvider([InMemoryUserProvider(), InMemoryUserProvider()])

    with pytest.raises(UserNotFoundError):
        _ = await chain.load_user_by_identifier("nobody")


def test_supports_class_asks_every_provider() -> None:
    chain = ChainUserProvider([InMemoryUserProvider()])

    assert chain.supports_class(InMemoryUser) is True
    assert chain.supports_class(str) is False


def test_get_providers_returns_them_in_order() -> None:
    first = InMemoryUserProvider()
    second = InMemoryUserProvider()
    chain = ChainUserProvider([first, second])

    assert chain.get_providers() == (first, second)


@pytest.mark.anyio
async def test_upgrade_password_fans_out_to_capable_providers() -> None:
    upgraded: list[tuple[str | None, str]] = []

    @final
    class Upgrading:
        async def load_user_by_identifier(self, identifier: str) -> UserInterface:
            return InMemoryUser(identifier)

        def supports_class(self, user_class: type) -> bool:
            return issubclass(user_class, InMemoryUser)

        async def upgrade_password(
            self,
            user: PasswordAuthenticatedUserInterface,
            new_hashed_password: str,
        ) -> None:
            upgraded.append((user.get_password(), new_hashed_password))

    chain = ChainUserProvider([Upgrading(), InMemoryUserProvider()])
    alice = InMemoryUser("alice", password="old-hash")  # noqa: S106 — a dummy hash fixture, not a secret

    await chain.upgrade_password(alice, "new-hash")

    assert upgraded == [("old-hash", "new-hash")]


@pytest.mark.anyio
async def test_upgrade_password_swallows_a_provider_that_turns_the_user_away() -> None:
    upgraded: list[str] = []

    @final
    class Refusing:
        async def load_user_by_identifier(self, identifier: str) -> UserInterface:
            return InMemoryUser(identifier)

        def supports_class(self, user_class: type) -> bool:
            return issubclass(user_class, InMemoryUser)

        async def upgrade_password(
            self,
            user: PasswordAuthenticatedUserInterface,
            new_hashed_password: str,
        ) -> None:
            del user, new_hashed_password
            raise UnsupportedUserError("no")

    @final
    class Accepting:
        async def load_user_by_identifier(self, identifier: str) -> UserInterface:
            return InMemoryUser(identifier)

        def supports_class(self, user_class: type) -> bool:
            return issubclass(user_class, InMemoryUser)

        async def upgrade_password(
            self,
            user: PasswordAuthenticatedUserInterface,
            new_hashed_password: str,
        ) -> None:
            del user
            upgraded.append(new_hashed_password)

    chain = ChainUserProvider([Refusing(), Accepting()])

    await chain.upgrade_password(InMemoryUser("alice"), "new-hash")

    assert upgraded == ["new-hash"]


@pytest.mark.anyio
async def test_attributes_are_forwarded_to_an_attributes_based_provider() -> None:
    seen: list[Mapping[str, object] | None] = []

    @final
    class Attributed(AttributesBasedUserProviderInterface):
        @override
        async def load_user_by_identifier(
            self,
            identifier: str,
            attributes: Mapping[str, object] | None = None,
        ) -> UserInterface:
            seen.append(attributes)
            return InMemoryUser(identifier)

        @override
        def supports_class(self, user_class: type) -> bool:
            return issubclass(user_class, InMemoryUser)

    chain = ChainUserProvider([Attributed()])

    _ = await chain.load_user_by_identifier("alice", {"scope": "read"})

    assert seen == [{"scope": "read"}]


@pytest.mark.anyio
async def test_a_plain_provider_is_not_handed_attributes() -> None:
    chain = ChainUserProvider([InMemoryUserProvider({"alice": InMemoryUser("alice")})])

    user = await chain.load_user_by_identifier("alice", {"scope": "read"})

    assert user.get_user_identifier() == "alice"
