"""The password-upgrader contract is satisfied structurally, and by the chain."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_security_core.user import ChainUserProvider, InMemoryUser, PasswordUpgraderInterface

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface


@final
class Upgrader:
    """A fake store that writes a rehashed password back."""

    def __init__(self) -> None:
        self.upgraded: list[str] = []

    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        del user
        self.upgraded.append(new_hashed_password)


def test_a_fake_upgrader_satisfies_the_contract() -> None:
    assert isinstance(Upgrader(), PasswordUpgraderInterface)


def test_something_without_the_method_does_not() -> None:
    assert not isinstance(object(), PasswordUpgraderInterface)


def test_the_chain_provider_is_an_upgrader() -> None:
    assert issubclass(ChainUserProvider, PasswordUpgraderInterface)


@pytest.mark.anyio
async def test_the_fake_records_what_it_was_asked_to_store() -> None:
    upgrader = Upgrader()

    await upgrader.upgrade_password(InMemoryUser("alice"), "new-hash")

    assert upgrader.upgraded == ["new-hash"]
