"""The chain step that carries an authenticated user across requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_foundation import Session, SessionStorageInterface
from xtr_logging_contracts import NullLogger
from xtr_security_core.authentication.authentication_trust_resolver import (
    AuthenticationTrustResolver,
)
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http._security_state import security_state_of
from xtr_security_http.event.token_deauthenticated_event import TokenDeauthenticatedEvent
from xtr_security_http.security_request_attributes import SecurityRequestAttributes

from ._user_refresh import UserRefresher
from .abstract_listener import AbstractListener

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_kernel.event.response_event import ResponseEvent
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.authentication_trust_resolver_interface import (
        AuthenticationTrustResolverInterface,
    )
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )
    from xtr_security_core.user.user_interface import UserInterface
    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from .refresh_user_result import RefreshUserResult

__all__ = ["ContextListener"]

# The spelling of the session key an application reads its security context
# under: the ``_security.`` prefix every user-facing key of this flow carries,
# followed by the firewall's own name. Two firewalls over one session keep
# their contexts apart by it, and a template or a view written against the
# spelling keeps working.
_SESSION_KEY_PREFIX: Final = "_security."


@final
class ContextListener(AbstractListener):
    """Reads the token a session carries into this request, and writes it back.

    A chain step for a stateful firewall: the session a request reattaches
    holds the token its login stored, and this listener restores it, reloads
    the user it carries through the firewall's providers — a session outlives
    the data it was minted from, so the user is read fresh every request —
    and deauthenticates the token when the reload changed the user: the
    password was changed elsewhere, a role was withdrawn, the account is gone.

    ``supports`` answers ``None`` always: nothing in a request's head commits
    this listener, but it wants its say on every request of a stateful
    firewall — the lazy join, so the chain runs it before it knows whether a
    session even holds a token.

    The response half — :meth:`on_response`, registered beside the chain on
    the kernel's response event — writes the token back: what the request
    authenticated is stored under the same session key, and an anonymous
    request's key is removed, so a logout does not linger in the session.
    It runs only for the requests this listener's own request half marked —
    the firewall-run mark, parked with the session key as its value — so a
    response of a request another firewall ran is left to that firewall's
    listener.

    The session is built from the request through the storage the application
    pointed the session at — the one request-to-session path — and parked on
    the request's security state, so both halves of one request reach the
    same session and nothing one request set reaches another.

    The user a token carries is a plain object here: the lazy-initialisation
    guard the upstream listener opens its response half with — a user
    materialised on first touch, initialized before it is stored — has no
    lazy user to guard on this stack, so it guards nothing; the token is
    stored as the object it is, and the session storage's own contract owns
    the wire format.
    """

    __slots__ = (
        "_context_key",
        "_dispatcher",
        "_logger",
        "_session_key",
        "_session_storage",
        "_token_storage",
        "_trust_resolver",
        "_user_providers",
    )

    def __init__(  # noqa: PLR0913 -- the upstream listener's own shape: the storage, the providers, the key, and the collaborators of the refresh
        self,
        token_storage: TokenStorageInterface,
        user_providers: Sequence[UserProviderInterface],
        context_key: str,
        session_storage: SessionStorageInterface,
        *,
        logger: LoggerInterface | None = None,
        dispatcher: EventDispatcherInterface | None = None,
        trust_resolver: AuthenticationTrustResolverInterface | None = None,
    ) -> None:
        """Build the listener over one firewall's session key and providers.

        Args:
            token_storage: Where the restored token is set for the request's
                own authentication to read.
            user_providers: The providers the session token's user is reloaded
                through, in order; the first that supports the user's class
                and vouches for it wins.
            context_key: The firewall's own name, composed into the session
                key its context is stored under.
            session_storage: Where the session's attributes are kept between
                requests; the session is built from the request through it.
            logger: Writes the refresh's decisions, when given.
            dispatcher: Where the refreshed-user check and the
                deauthentication are announced, when given.
            trust_resolver: Reads whether the response half's token is
                authenticated; the base resolver when none is given.

        Raises:
            InvalidArgumentError: When ``context_key`` is empty — the session
                key it composes would name no firewall, and two firewalls
                would share one context.
        """
        if not context_key:
            raise InvalidArgumentError("The context listener's context key must not be empty.")
        self._token_storage = token_storage
        self._user_providers = tuple(user_providers)
        self._context_key = context_key
        self._session_key = f"{_SESSION_KEY_PREFIX}{context_key}"
        self._session_storage = session_storage
        self._logger = logger or NullLogger()
        self._dispatcher = dispatcher
        self._trust_resolver = trust_resolver or AuthenticationTrustResolver()

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer the lazy join: ``None``, on every request.

        Nothing in a request's head commits this listener — the session is
        read, not the request — so it never answers ``True``, and it never
        skips: a stateful firewall restores its context on every request,
        token or no token, because the *absence* of one is what the request
        half leaves in the storage for the access decision to weigh.
        """
        del request
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Restore the token the request's session carries, refreshed through the providers.

        The session is built from the request and parked on its security
        state, beside the firewall-run mark that gates the response half —
        both under this listener's own key, so a second firewall's listener
        answers for its requests alone. A session holding no token, or one
        holding something else — a corrupt payload, a foreign class —
        leaves the storage empty: the request goes on anonymous, and the
        access decision is what turns it away.

        A token the session holds is refreshed before it is stored: its user
        is reloaded through the providers, and a reload that changed the
        user deauthenticates — the token is not stored, and the
        deauthentication is announced with the reason and the providers that
        contributed to it.

        Raises:
            InvalidArgumentError: When a session token carries no user — the
                session was written by something that stored a token no
                authentication could have produced.
            UnsupportedUserError: When no user provider supports the class
                of the user the session token carries.
        """
        request = request_event.request
        state = security_state_of(request_event.state)
        session = Session.from_request(request, self._session_storage)
        state.attributes[SecurityRequestAttributes.SESSION] = session
        state.attributes[SecurityRequestAttributes.FIREWALL_RUN] = self._session_key

        token = await session.get(self._session_key)
        if token is None:
            self._token_storage.set_token(None)
            return
        if not isinstance(token, TokenInterface):
            self._logger.warning(
                "Expected a security token from the session, got something else.",
                {"key": self._session_key, "received": type(token).__name__},
            )
            self._token_storage.set_token(None)
            return
        user = token.get_user()
        if user is None:
            raise InvalidArgumentError(
                f"Cannot authenticate a {type(token).__name__} token because it stores no user.",
            )

        original_token = token
        result = await self._refresh_user(token, user)
        if result.token is None:
            self._logger.debug("Token was deauthenticated after trying to refresh it.")
            if self._dispatcher is not None:
                _ = await self._dispatcher.dispatch(
                    TokenDeauthenticatedEvent(
                        original_token,
                        request,
                        result.deauthentication_reason,
                        result.provider_classes,
                        result.exception,
                    ),
                )
            self._token_storage.set_token(None)
            return
        self._token_storage.set_token(result.token)

    async def on_response(self, response_event: ResponseEvent) -> None:
        """Store what the request authenticated back into the session it reattached.

        Runs only for the requests this listener's request half marked with
        its own session key: a response of a request another firewall ran —
        or none at all — is left alone. An authenticated token is stored
        under the session key; an anonymous request's key is removed, so a
        logout does not linger in the session and answer for the next
        request.
        """
        state = security_state_of(response_event.state)
        if state.attributes.get(SecurityRequestAttributes.FIREWALL_RUN) != self._session_key:
            return
        session = state.attributes.get(SecurityRequestAttributes.SESSION)
        if not isinstance(session, Session):
            return
        token = self._token_storage.get_token()
        if not self._trust_resolver.is_authenticated(token):
            _ = await session.remove(self._session_key)
            return
        await session.set(self._session_key, token)

    async def _refresh_user(self, token: TokenInterface, user: UserInterface) -> RefreshUserResult:
        """Reload ``token``'s ``user`` through the providers, deauthenticating on a change.

        The whole provider loop — the skipping, the weighing, the
        deauthentication reasons — lives on the refresher this listener
        builds; see
        :class:`~xtr_security_http.firewall._user_refresh.UserRefresher`.

        Raises:
            UnsupportedUserError: When no provider supports the class of
                the user the token carries.
        """
        return await UserRefresher(self._user_providers, self._logger, self._dispatcher).refresh(
            token,
            user,
        )
