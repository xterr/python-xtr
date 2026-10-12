"""Access tokens kept in this process."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)

from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface

__all__ = ["AccessTokenManager"]


@final
class AccessTokenManager(AccessTokenManagerInterface):
    """Holds the access tokens in a mapping, for one process.

    For tests and single-process demonstrations: everything stored goes when
    the process does, and a second process shares none of it.

    A deployment that does not persist its access tokens builds this with
    ``persist_access_token`` off, and then storing is a no-op and nothing is
    ever found — which is exactly what the storage-free deployment looks like,
    so the same wiring works for both.
    """

    def __init__(self, clock: ClockInterface, persist_access_token: bool = True) -> None:
        """Read expiry against ``clock``; store nothing when not persisting."""
        self._clock = clock
        self._persist_access_token = persist_access_token
        self._access_tokens: dict[str, AccessTokenInterface] = {}

    @override
    def __repr__(self) -> str:
        """Name the type and how many tokens are held, never which."""
        return f"{type(self).__name__}(held={len(self._access_tokens)})"

    @override
    async def find(self, identifier: str) -> AccessTokenInterface | None:
        """Return the token stored as ``identifier``, or ``None``."""
        if not self._persist_access_token:
            return None

        return self._access_tokens.get(identifier)

    @override
    async def save(self, access_token: AccessTokenInterface) -> None:
        """Store ``access_token``, new or already known."""
        if not self._persist_access_token:
            return

        self._access_tokens[access_token.get_identifier()] = access_token

    @override
    async def clear_expired(self) -> int:
        """Forget every token that has expired, and return how many went.

        A token expiring at this very instant is kept: it is still being
        accepted, and sweeping it would refuse a request the server would
        otherwise have honoured.
        """
        if not self._persist_access_token:
            return 0

        now = self._clock.now()
        kept = {
            identifier: token
            for identifier, token in self._access_tokens.items()
            if token.get_expiry() >= now
        }
        cleared = len(self._access_tokens) - len(kept)
        self._access_tokens = kept

        return cleared
