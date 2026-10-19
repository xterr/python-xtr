"""The pending OIDC login attempts a session carries, capped."""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Final, cast, final

if TYPE_CHECKING:
    from xtr_http_foundation import Session

__all__ = ["OidcLoginAttempts"]

_MAX_CONCURRENT_ATTEMPTS: Final = 5
"""The most pending attempts a session may carry.

Each pending attempt lives under its own session key, carrying the state, so
that concurrent logins started from several tabs write distinct entries
instead of rewriting a shared one; the count is capped, oldest attempts
dropped first, so that an unauthenticated visitor cannot grow the session
unbounded (an unbounded per-state store was CVE-2021-22119 elsewhere)."""


@final
class OidcLoginAttempts:
    """Reads, adds and consumes the pending OIDC login attempts of one session.

    The attempts are keyed by the ``state`` the authorization request sent,
    under ``_security.oidc_login.<firewall>.attempt.<state>``. The local
    session contract exposes no enumeration of its attribute names, so the
    pending states are tracked in an index attribute under the same prefix —
    the one local difference from the upstream store, which walks the
    session's keys; the cap and the consumption semantics are the same.
    """

    __slots__ = ("_index_key", "_prefix", "_session")

    def __init__(self, session: Session, firewall_name: str) -> None:
        """Record the session and the prefix the firewall's attempts live under."""
        self._session = session
        self._prefix = f"_security.oidc_login.{firewall_name}."
        self._index_key = f"{self._prefix}attempts"

    async def add(
        self,
        state: str,
        nonce: str,
        code_verifier: str | None,
        redirect_uri: str,
    ) -> None:
        """Store one pending attempt, dropping the oldest ones past the cap.

        The cap is enforced before the new attempt is stored, so a session
        never carries more than :data:`_MAX_CONCURRENT_ATTEMPTS` of them.
        """
        states = await self._states()
        while len(states) >= _MAX_CONCURRENT_ATTEMPTS:
            oldest = states.pop(0)
            _ = await self._session.remove(self._key(oldest))
        states.append(state)
        await self._session.set(self._index_key, states)
        await self._session.set(
            self._key(state),
            {
                "nonce": nonce,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            },
        )

    async def take(self, state: str) -> dict[str, object] | None:
        """Return and consume the attempt ``state`` names, or ``None`` when none matches.

        The lookup compares the stored states in constant time, so the
        caller-supplied value is never used as a session key, and an unknown
        state reads the same as an empty session — no oracle, no login CSRF.
        The matched attempt is consumed whatever the caller does with it: a
        replayed callback fails on the state check, and the other pending
        attempts survive.
        """
        states = await self._states()
        for stored in states:
            if not hmac.compare_digest(stored, state):
                continue
            key = self._key(stored)
            attempt = await self._session.get(key)
            _ = await self._session.remove(key)
            states.remove(stored)
            await self._session.set(self._index_key, states)
            if isinstance(attempt, dict):
                # The attempt was stored by add(), as a mapping of strings.
                return cast("dict[str, object]", attempt)
            return None
        return None

    async def clear(self) -> None:
        """Drop every pending attempt.

        Each carries a nonce and a PKCE verifier, which have no place in an
        authenticated session; a callback for one of them would re-authenticate
        anyway, the state check just fails it earlier.
        """
        states = await self._states()
        for stored in states:
            _ = await self._session.remove(self._key(stored))
        await self._session.set(self._index_key, [])

    async def _states(self) -> list[str]:
        """Return the pending states, oldest first, as the index attribute carries them."""
        states = await self._session.get(self._index_key)
        # The index was stored by add(), as a list of states.
        return cast("list[str]", states) if isinstance(states, list) else []

    def _key(self, state: str) -> str:
        """Return the session key one attempt lives under."""
        return f"{self._prefix}attempt.{state}"
