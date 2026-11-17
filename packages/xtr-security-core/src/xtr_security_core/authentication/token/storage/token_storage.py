"""The token storage: one token per unit of work, each unit holding its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from .token_storage_interface import TokenStorageInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["TokenStorage"]


@final
class TokenStorage(TokenStorageInterface, ResetInterface):
    """Holds the current token of one unit of work.

    A scoped service: one instance per request, message or command, so two
    units of work never see each other's token. Its isolation comes from that
    scope alone — each unit is built a fresh, empty instance, and the instance
    goes with the unit. The container's resetter never touches it: it resets
    singletons only, since resetting a scoped instance from whichever unit
    ended first would clear the token of another still running.

    It still satisfies
    :class:`~xtr_service_contracts.reset_interface.ResetInterface`, for an
    owner that holds one instance across several units of its own — a hand-built
    storage reused between tasks — and must clear it itself in between. It
    declares no ``__slots__``, so instances stay weakly referenceable.

    An initializer, when set, runs once — the first time the token is read, or
    just before one is stored — so the token can be produced lazily, only when
    something actually asks for it.
    """

    _token: TokenInterface | None
    _initializer: Callable[[], None] | None

    def __init__(self) -> None:
        """Start with no token."""
        self._token = None
        self._initializer = None

    @override
    def get_token(self) -> TokenInterface | None:
        """Return the current token, or ``None`` when none was set.

        A pending initializer runs first, once.
        """
        initializer = self._initializer
        if initializer is not None:
            self._initializer = None
            initializer()
        return self._token

    @override
    def set_token(self, token: TokenInterface | None) -> None:
        """Store ``token`` as the current one, or clear it with ``None``.

        Storing a token runs any pending initializer first, so it cannot
        overwrite the token later; either way the initializer is dropped.
        """
        if token is not None:
            _ = self.get_token()
        self._initializer = None
        self._token = token

    def set_initializer(self, initializer: Callable[[], None] | None) -> None:
        """Set the callable that produces the token the first time it is needed, or clear it."""
        self._initializer = initializer

    @override
    async def reset(self) -> None:
        """Forget the current token, so the next unit of work starts clean."""
        self.set_token(None)
