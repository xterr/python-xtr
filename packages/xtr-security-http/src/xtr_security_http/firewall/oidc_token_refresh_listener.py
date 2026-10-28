"""The chain step that renews the OIDC tokens a logged-in user's token carries."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import NullLogger
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.decorator.firewall_listener_order import FirewallListenerOrder
from xtr_security_http.exception import OidcInvalidGrantError

from .abstract_listener import AbstractListener
from .context_listener import ContextListener

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_security_core.authentication.token.storage.token_storage_interface import (
        TokenStorageInterface,
    )

    from xtr_security_http.oidc.oidc_token_refresher import OidcTokenRefresher

__all__ = ["OidcTokenRefreshListener"]


@final
@FirewallListenerOrder(after=ContextListener)
class OidcTokenRefreshListener(AbstractListener):
    """Renews the OIDC access tokens of the logged-in user before they expire.

    A chain step for a stateful firewall whose logins went through the OIDC
    login: the token the context step restored from the session carries the
    access and refresh tokens the provider issued, and this step hands it to
    the refresher, which renews the access token once it comes within the
    refresher's leeway of expiring. It runs after the context step — declared
    through ``@FirewallListenerOrder``, at the priority the two share — so
    what it renews is the token the request reads and the context step's
    response half writes back into the session.

    Failing to renew only ends the login when the provider says the refresh
    token is gone for good: the refresher's invalid-grant error clears the
    token from the storage — the request goes on anonymous, and the context
    step's response half removes the session's copy with it — while any other
    renewal failure is only warned about and left for the next request, the
    tokens untouched. A provider that cannot be reached would otherwise log
    every user out at once.

    The refresher this step hands the token to stays a typing-only
    reference: importing the OIDC client machinery it lives in would pull
    the JOSE toolkit behind the ``oidc`` extra into every application
    importing this package, listener or no listener. The wiring that builds
    this step resolves the class where the extra is already required.
    """

    __slots__ = ("_logger", "_refresher", "_token_storage")

    def __init__(
        self,
        token_storage: TokenStorageInterface,
        refresher: OidcTokenRefresher,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Build the step over the request's token storage and the token refresher.

        Args:
            token_storage: Where the context step restored the request's
                token; the renewal reads it, and a rejected grant clears it.
            refresher: Renews the OIDC tokens the stored token carries.
            logger: Writes the renewal's outcomes, when given.
        """
        self._token_storage = token_storage
        self._refresher = refresher
        self._logger = logger or NullLogger()

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer the lazy join: ``None``, on every request.

        The chain asks ``supports`` before the context step has restored the
        token, so the storage this step would have to decide on is still
        empty: answering about the token here would skip this step on every
        request. ``None`` keeps the join lazy, and :meth:`authenticate` is
        the one that reads the storage.
        """
        del request
        return None

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Renew the OIDC tokens the stored token carries, when they are due.

        A request with no token stored — an anonymous one, or a firewall that
        restored none — is left alone. A token the refresher renews is
        renewed in place: it keeps its seat in the storage, and the context
        step's response half writes the renewed attributes back into the
        session. A refresh token the provider no longer honors clears the
        storage — the one failure that ends the login — and any other
        renewal failure is logged and left for the next request, so an
        unreachable provider costs a warning per request, not every user's
        login.
        """
        del request_event
        token = self._token_storage.get_token()
        if token is None:
            return
        try:
            if await self._refresher.refresh_if_needed(token):
                self._logger.debug("Renewed the OIDC access token of the logged-in user.")
        except OidcInvalidGrantError as error:
            self._logger.info(
                "The OIDC provider no longer honors the refresh token; logging the user out.",
                {"exception": error},
            )
            self._token_storage.set_token(None)
        except AuthenticationError as error:
            # The renewal is tried again on the next request, the tokens
            # left exactly as they were.
            self._logger.warning(
                "Could not renew the OIDC access token of the logged-in user.",
                {"exception": error},
            )
