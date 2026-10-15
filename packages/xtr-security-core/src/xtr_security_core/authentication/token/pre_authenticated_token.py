"""A token for a user the request itself already authenticated."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.exception import InvalidArgumentError

from .abstract_token import AbstractToken

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["PreAuthenticatedToken"]


@final
class PreAuthenticatedToken(AbstractToken):
    """A user proven by the request itself, the firewall that read it, and the roles.

    Some requests carry the authenticated identity in themselves — a trusted
    header, a certificate, a pre-shared key. This is the token an
    authenticator settles on for those: the user, the firewall that read the
    identity, and the roles fixed at that moment.

    Attributes:
        firewall_name: The firewall (or unit of work) that read the identity.
    """

    __slots__: tuple[str, ...] = ("_firewall_name",)

    _firewall_name: str

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str] = (),
    ) -> None:
        """Record the user, the firewall that read their identity, and the roles.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        super().__init__(roles)
        if firewall_name == "":
            raise InvalidArgumentError('The "firewall_name" must not be empty.')
        self._firewall_name = firewall_name
        self.set_user(user)

    def get_firewall_name(self) -> str:
        """Return the firewall (or unit of work) that read the user's identity."""
        return self._firewall_name
