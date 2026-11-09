"""The token authentication settles on once a user is established."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["PostAuthenticationToken"]


class PostAuthenticationToken(AbstractToken):
    """A user, the firewall that authenticated them, and the roles decided.

    The ordinary outcome of a successful authentication. It lives in the core,
    not only at the HTTP edge, because a worker or a command authenticates the
    same way — it sets one of these on the token storage without a request ever
    being involved.

    A session keeps it with its firewall beside the roles and the attributes —
    the tokens an OIDC login stamps on it included, as the plain JSON of the
    session store.

    Attributes:
        firewall_name: The firewall (or unit of work) that authenticated.
    """

    _firewall_name: str

    def __init__(
        self,
        user: UserInterface,
        firewall_name: str,
        roles: Sequence[str],
    ) -> None:
        """Record the user, the firewall that authenticated them, and their roles.

        Raises:
            InvalidArgumentError: When ``firewall_name`` is empty.
        """
        super().__init__(roles)
        if firewall_name == "":
            raise InvalidArgumentError('The "firewall_name" must not be empty.')
        self._firewall_name = firewall_name
        self.set_user(user)

    def get_firewall_name(self) -> str:
        """Return the firewall (or unit of work) that authenticated the user."""
        return self._firewall_name

    @override
    def to_session(
        self,
        encode_token: Callable[[TokenInterface], dict[str, object]],
    ) -> dict[str, object]:
        """Return the roles, the attributes and the firewall, for a session to keep."""
        return {**super().to_session(encode_token), "firewall": self._firewall_name}

    @classmethod
    @override
    def from_session(
        cls,
        state: Mapping[str, object],
        user: UserInterface | None,
        decode_token: Callable[[object], TokenInterface | None],
    ) -> Self:
        """Rebuild the token a session kept, its firewall included.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of
                the wrong type, or the firewall is empty.
        """
        firewall = state.get("firewall")
        if not isinstance(firewall, str) or firewall == "":
            raise InvalidArgumentError(
                'The session state\'s "firewall" must be a non-empty string.',
            )
        token = super().from_session(state, user, decode_token)
        token._firewall_name = firewall  # noqa: SLF001 -- the token this very class rebuilds
        return token
