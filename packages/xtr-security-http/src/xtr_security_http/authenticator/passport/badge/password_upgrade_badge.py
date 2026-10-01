"""A badge asking that a verified password be re-stored under a fresh hash."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .badge_interface import BadgeInterface

if TYPE_CHECKING:
    from xtr_security_core.user.password_upgrader_interface import PasswordUpgraderInterface

__all__ = ["PasswordUpgradeBadge"]


@final
class PasswordUpgradeBadge(BadgeInterface):
    """Carries the plaintext and the place to write its upgraded hash to.

    Added to a passport when a password verified against an outdated hash, so
    the migrating listener can re-hash the plaintext with the current
    algorithm and hand it to an upgrader to store. It resolves on its own — an
    upgrade is opportunistic, never a condition of authentication.

    Attributes:
        plaintext_password: The verified plaintext, to be re-hashed.
        password_upgrader: Where the fresh hash is written, when one is known.
    """

    __slots__ = ("_password_upgrader", "_plaintext_password")

    def __init__(
        self,
        plaintext_password: str,
        password_upgrader: PasswordUpgraderInterface | None = None,
    ) -> None:
        """Record the plaintext and, when known, where to store its new hash."""
        self._plaintext_password = plaintext_password
        self._password_upgrader = password_upgrader

    def get_and_erase_plaintext_password(self) -> str:
        """Return the plaintext once, then drop it so it is not held longer."""
        plaintext = self._plaintext_password
        self._plaintext_password = ""
        return plaintext

    def get_password_upgrader(self) -> PasswordUpgraderInterface | None:
        """Return the upgrader the new hash is written to, if one was set."""
        return self._password_upgrader

    def set_password_upgrader(self, password_upgrader: PasswordUpgraderInterface) -> None:
        """Set the upgrader the migrating listener writes the new hash to."""
        self._password_upgrader = password_upgrader

    @override
    def is_resolved(self) -> bool:
        """Report resolved always: an upgrade never gates authentication."""
        return True
