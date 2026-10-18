"""The default session strategy: what a login does to the session it reattached."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_foundation import Session

from xtr_security_http._security_state import security_state_of, state_bag_of
from xtr_security_http.exception import InvalidSessionStrategyError, MissingSessionError
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from .session_authentication_strategy_interface import SessionAuthenticationStrategyInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_csrf import ClearableTokenStorageInterface

__all__ = ["SessionAuthenticationStrategy"]


@final
class SessionAuthenticationStrategy(SessionAuthenticationStrategyInterface):
    """What a successful login does to the session the request reattached.

    Three answers, one per strategy name:

    - ``NONE`` — the session is left as it is: the ID it reattached under
      is kept, for a firewall whose every request authenticates on its
      own and the session is only a carrier.
    - ``MIGRATE`` — the session's attributes are carried to a fresh ID
      and the entry under the old one destroyed: a session fixation —
      an ID an attacker planted before the login — stops answering for
      the account the login just named. The CSRF tokens minted under
      the old ID are dropped with it, through the clearable token
      storage, so a value stolen before the rotation cannot answer after
      it.
    - ``INVALIDATE`` — the session is emptied and its entry destroyed:
      nothing of the session before the login survives it.

    The session is the one the request's security state carries — the
    one the context listener built from the request and parked there —
    so the ID this strategy rotates is the ID the response half writes
    the token back under, and not a second session built beside it.

    An unknown strategy name is refused when the strategy is asked to
    act, not when it is built: the name is the application's
    configuration, and a configuration error is heard the first time the
    configured thing runs.
    """

    NONE: Final[str] = "none"
    """The session is not changed."""

    MIGRATE: Final[str] = "migrate"
    """The session's ID is rotated, its attributes kept."""

    INVALIDATE: Final[str] = "invalidate"
    """The session's ID is rotated, its attributes dropped."""

    __slots__ = ("_csrf_token_storage", "_strategy")

    def __init__(
        self,
        strategy: str,
        csrf_token_storage: ClearableTokenStorageInterface | None = None,
    ) -> None:
        """Record the strategy name and the CSRF storage a rotation clears.

        Args:
            strategy: One of :attr:`NONE`, :attr:`MIGRATE`,
                :attr:`INVALIDATE`.
            csrf_token_storage: The clearable CSRF token storage, emptied
                when a migration rotates the session — the tokens minted
                under the old ID must not answer for the new. Only the
                migration clears it; the other strategies leave the
                storage alone.
        """
        self._strategy = strategy
        self._csrf_token_storage = csrf_token_storage

    @override
    async def on_authentication(
        self,
        request: ServerRequestInterface,
        token: TokenInterface,
    ) -> None:
        """Move the request's session the way the configured strategy names.

        Args:
            request: The request that authenticated, carrying the session
                on its security state.
            token: The token the authentication settled on; the strategy
                itself does not read it, but a strategy of an application's
                own may.

        Raises:
            MissingStateBagError: When the request carries no state bag —
                no firewall chain ran for it.
            MissingSessionError: When the request's security state carries
                no session — no stateful context listener ran for it, so
                there is no session for the strategy to move.
            InvalidSessionStrategyError: When the configured strategy name
                is none of the three.
        """
        del token
        session = self._session_of(request)
        strategy = self._strategy
        if strategy == self.NONE:
            return
        if strategy == self.MIGRATE:
            await session.migrate(destroy_old=True)
            if self._csrf_token_storage is not None:
                await self._csrf_token_storage.clear()
            return
        if strategy == self.INVALIDATE:
            await session.invalidate()
            return
        raise InvalidSessionStrategyError(strategy)

    def _session_of(self, request: ServerRequestInterface) -> Session:
        """Return the session the request's security state carries.

        The one session of the request — the context listener's park — or
        a loud refusal when the stateful machinery never ran: a strategy
        asked to move a session that does not exist is a wiring error,
        and a silent no-op would leave a login unrotated while reading as
        protected.
        """
        state = security_state_of(state_bag_of(request))
        session = state.attributes.get(SecurityRequestAttributes.SESSION)
        if not isinstance(session, Session):
            raise MissingSessionError(
                "The request's security state carries no session: no stateful "
                "context listener ran for it, so there is no session for the "
                "strategy to move.",
            )
        return session
