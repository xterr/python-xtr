"""The password-upgrade badge carries the plaintext and where to store its new hash."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

from xtr_security_http.authenticator.passport.badge.password_upgrade_badge import (
    PasswordUpgradeBadge,
)

if TYPE_CHECKING:
    from xtr_password_hasher import PasswordAuthenticatedUserInterface


class _Upgrader(PasswordUpgraderInterface):
    @override
    async def upgrade_password(
        self,
        user: PasswordAuthenticatedUserInterface,
        new_hashed_password: str,
    ) -> None:
        del user, new_hashed_password


def test_it_is_always_resolved() -> None:
    assert PasswordUpgradeBadge("secret").is_resolved() is True


def test_the_plaintext_is_read_once_then_dropped() -> None:
    badge = PasswordUpgradeBadge("secret")

    assert badge.get_and_erase_plaintext_password() == "secret"
    assert badge.get_and_erase_plaintext_password() == ""


def test_the_upgrader_is_recorded_and_readable() -> None:
    upgrader = _Upgrader()
    badge = PasswordUpgradeBadge("secret", upgrader)

    assert badge.get_password_upgrader() is upgrader


def test_the_upgrader_can_be_set_after_construction() -> None:
    upgrader = _Upgrader()
    badge = PasswordUpgradeBadge("secret")

    assert badge.get_password_upgrader() is None
    badge.set_password_upgrader(upgrader)
    assert badge.get_password_upgrader() is upgrader
