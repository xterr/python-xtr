"""Authorization codes kept in this process."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import (
    ClockInterface,  # noqa: TC002 -- container hydrates this constructor at runtime
)

from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.authorization_code_interface import (
        AuthorizationCodeInterface,
    )

__all__ = ["AuthorizationCodeManager"]


@final
class AuthorizationCodeManager(AuthorizationCodeManagerInterface):
    """Holds the authorization codes in a mapping, for one process.

    For tests and single-process demonstrations. Codes are the shortest-lived
    thing this server stores, so losing them with the process costs least of
    all — a client simply starts the flow again.
    """

    def __init__(self, clock: ClockInterface) -> None:
        """Read expiry against ``clock``."""
        self._clock = clock
        self._authorization_codes: dict[str, AuthorizationCodeInterface] = {}

    @override
    def __repr__(self) -> str:
        """Name the type and how many codes are held, never which."""
        return f"{type(self).__name__}(held={len(self._authorization_codes)})"

    @override
    async def find(self, identifier: str) -> AuthorizationCodeInterface | None:
        """Return the code stored as ``identifier``, or ``None``."""
        return self._authorization_codes.get(identifier)

    @override
    async def save(self, auth_code: AuthorizationCodeInterface) -> None:
        """Store ``auth_code``, new or already known."""
        self._authorization_codes[auth_code.get_identifier()] = auth_code

    @override
    async def clear_expired(self) -> int:
        """Forget every code that has expired, and return how many went.

        A code expiring at this very instant is kept: it is still redeemable.
        """
        now = self._clock.now()
        kept = {
            identifier: code
            for identifier, code in self._authorization_codes.items()
            if code.get_expiry() >= now
        }
        cleared = len(self._authorization_codes) - len(kept)
        self._authorization_codes = kept

        return cleared
