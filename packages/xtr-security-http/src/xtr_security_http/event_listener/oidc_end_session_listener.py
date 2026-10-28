"""Handling RP-Initiated Logout by redirecting to the provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final
from urllib.parse import quote, urlencode

from typing_extensions import override
from xtr_event_dispatcher import EventSubscriberInterface
from xtr_logging_contracts import NullLogger
from xtr_security_core.exception import AuthenticationError

from xtr_security_http.event.logout_event import LogoutEvent

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher import SubscribedEvents
    from xtr_logging_contracts import LoggerInterface

    from xtr_security_http.http_utils import HttpUtils
    from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

__all__ = ["OidcEndSessionListener"]

_ID_TOKEN_ATTRIBUTE: Final = "oidc_id_token"  # noqa: S105 -- an attribute name, not a credential
"""Where the firewall keeps the ID token the provider issued."""


@final
class OidcEndSessionListener(EventSubscriberInterface):
    """Handles RP-Initiated Logout by redirecting to the provider.

    The logout redirects to the ``end_session_endpoint`` of the OIDC
    provider, so the provider ends its own session of the login too. The
    redirect carries the ID token the login keeps as its ``id_token_hint``
    — the provider knows from it which session of which client is being
    asked to end — and the page to come back to, when one is configured.
    """

    __slots__ = ("_discovery", "_http_utils", "_logger", "_post_logout_redirect_path")

    def __init__(
        self,
        discovery: OidcDiscovery,
        http_utils: HttpUtils,
        post_logout_redirect_path: str | None = None,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Record where the end-session endpoint is read, and how the redirect is built.

        Args:
            discovery: Reads the ``end_session_endpoint`` off the
                provider's discovery document.
            http_utils: Builds the redirect, and writes the URI the
                post-logout page becomes.
            post_logout_redirect_path: The page the provider sends the
                caller back to once it ended its session, or ``None`` to
                leave the landing to the provider.
            logger: Writes the fallback to a local logout, when given.
        """
        self._discovery = discovery
        self._http_utils = http_utils
        self._post_logout_redirect_path = post_logout_redirect_path
        self._logger = logger or NullLogger()

    @classmethod
    @override
    def get_subscribed_events(cls) -> Mapping[str | type, SubscribedEvents]:
        """Listen to a logout, ahead of the default logout listener that answers it."""
        return {LogoutEvent: ("on_logout", 65)}

    async def on_logout(self, event: LogoutEvent) -> None:
        """Redirect to the provider's end-session endpoint, unless a listener answered first.

        A login carrying no OIDC ID token is left to the listeners that
        answer a local logout. A provider that announces no usable
        ``end_session_endpoint`` — or one that cannot be reached — leaves
        the logout a local one too: the default logout listener answers it,
        and logging out of the application never depends on the provider
        being up.
        """
        # a listener registered earlier already decided the logout response, and
        # whoever sets it first wins, as for the default logout response
        if event.get_response() is not None:
            return

        token = event.get_token()
        if token is None or not token.has_attribute(_ID_TOKEN_ATTRIBUTE):
            return

        id_token = token.get_attribute(_ID_TOKEN_ATTRIBUTE)
        if not isinstance(id_token, str):
            return

        try:
            end_session_endpoint = await self._discovery.get_secure_endpoint(
                "end_session_endpoint",
            )
        except AuthenticationError as error:
            # logging out of the application must not depend on the provider being
            # reachable and correctly configured, so the logout stays a local one
            self._logger.warning(
                'The OIDC provider does not announce a usable "end_session_endpoint"; '
                "falling back to a local logout.",
                {"exception": error},
            )
            return

        params: dict[str, str] = {"id_token_hint": id_token}

        if self._post_logout_redirect_path is not None:
            params["post_logout_redirect_uri"] = self._http_utils.generate_uri(
                self._post_logout_redirect_path,
            )

        separator = "&" if "?" in end_session_endpoint else "?"
        end_session_url = end_session_endpoint + separator + urlencode(params, quote_via=quote)

        event.set_response(
            self._http_utils.create_redirect_response(event.get_request(), end_session_url),
        )
