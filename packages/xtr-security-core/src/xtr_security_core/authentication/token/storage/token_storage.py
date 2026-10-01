"""The token storage: one token per unit of work, cleared between them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from .token_storage_interface import TokenStorageInterface

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["TokenStorage"]


@final
class TokenStorage(TokenStorageInterface, ResetInterface):
    """Holds the current token, and returns to empty between units of work.

    A scoped service: one instance per request, message or command, so two
    units of work never see each other's token. It satisfies
    :class:`~xtr_service_contracts.reset_interface.ResetInterface` — a
    container clears it when a unit of work ends, so the next starts with no
    token — and is weakly referenceable because it declares no ``__slots__``,
    so instances carry the ``__weakref__`` a kernel that resets its scoped
    services requires.
    """

    _token: TokenInterface | None

    def __init__(self) -> None:
        """Start with no token."""
        self._token = None

    @override
    def get_token(self) -> TokenInterface | None:
        """Return the current token, or ``None`` when none was set."""
        return self._token

    @override
    def set_token(self, token: TokenInterface | None) -> None:
        """Store ``token`` as the current one, or clear it with ``None``."""
        self._token = token

    @override
    def reset(self) -> None:
        """Forget the current token, so the next unit of work starts clean."""
        self._token = None
