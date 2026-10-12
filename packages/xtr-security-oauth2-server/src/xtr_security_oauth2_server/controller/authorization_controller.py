"""The endpoint a resource owner's browser arrives at."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)
from xtr_logging_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    LoggerInterface,
)
from xtr_security import Security  # noqa: TC002 -- container hydrates this constructor at runtime
from xtr_security_oauth2_server_core.authorization_server import (  # noqa: TC002 -- container hydrates this constructor at runtime
    AuthorizationServer,
)
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.redirect_uri import redirect_uri_carrying

from xtr_security_oauth2_server.converter.user_converter_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    UserConverterInterface,
)
from xtr_security_oauth2_server.event.authorization_request_resolve_event_factory import (  # noqa: TC001 -- container hydrates this constructor at runtime
    AuthorizationRequestResolveEventFactory,
)
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- container hydrates this constructor at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

from ._served_response import served

if TYPE_CHECKING:
    from xtr_http_kernel.bridge import Response
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )

__all__ = ["AuthorizationController"]

#: The code-challenge method that sends the verifier unhashed. A client may
#: only use it when its registration says so.
_PLAIN: Final = "plain"

#: What a client is told when nobody is authenticated. It says what happened
#: and nothing about how this deployment is put together: a client learning
#: that no firewall stands in front of the authorization endpoint learns
#: something about the server, which is never its business.
_NOBODY_TO_ASK: Final = (
    "No resource owner is authenticated on this request, so there is nobody to ask for consent."
)

#: What is written where the deployment can read it. The client is told
#: nothing about how this server is put together, so this is the only place
#: the commonest cause of a refusal — no firewall in front of the
#: authorization endpoint — can be named.
_UNCLAIMED_ENDPOINT: Final = (
    "An authorization request reached this server with no resource owner authenticated, so "
    "consent was never asked for and the request was refused. Put an application-level "
    "Firewall() on the application serving these endpoints, so the authorization endpoint "
    "establishes the resource owner; see this package's 'Use in an application' section."
)


@final
class AuthorizationController:
    """Reads an authorization request, asks the deployment, and answers the browser.

    The one endpoint a person reaches rather than a client. It reads the
    request, refuses it outright when it is malformed, and then has to ask a
    question this package cannot answer: does *this* resource owner agree to
    *this* client holding *these* scopes. That question goes out as an event,
    and the deployment answers it either by resolving the request or by
    answering the browser itself — which is how a consent page is shown, and
    how the form posting back reaches this endpoint a second time.

    Nothing is remembered between the two passes. The consent form posts the
    original query back, so the second pass reads the same request, reaches the
    same listener, and this time is approved. That is what lets the endpoint sit
    behind a firewall that keeps no session.

    A refusal is delivered the way the flow it belongs to delivers one: to the
    redirect URI when the request named a usable one, in the fragment when the
    flow answers in the fragment, and as a plain document when there is nowhere
    safe to send it.

    Nobody being authenticated is one of those refusals, and the commonest
    cause of it is a deployment that put no firewall in front of this
    endpoint: the router this package ships carries no dependency of its own,
    so an application mounts one — see the package's *Use in an application*
    section. The client is told only that there was nobody to ask; what the
    deployment has to do about it is written to the log, where a deployment
    reads it and a client never does.
    """

    __slots__ = (
        "_client_manager",
        "_dispatcher",
        "_event_factory",
        "_logger",
        "_security",
        "_server",
        "_user_converter",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- these six together are one endpoint
        self,
        server: AuthorizationServer,
        dispatcher: EventDispatcherInterface,
        event_factory: AuthorizationRequestResolveEventFactory,
        user_converter: UserConverterInterface,
        client_manager: ClientManagerInterface,
        security: Security,
        logger: LoggerInterface | None = None,
    ) -> None:
        """Answer authorization requests on ``server``, asking through ``dispatcher``.

        Args:
            server: What reads and completes the authorization request.
            dispatcher: Where the deployment is asked for the owner's decision.
            event_factory: What builds that question out of the request.
            user_converter: Turns the firewall's user into the resource owner a
                token names.
            client_manager: Where the client's registration is read from, to
                see whether it may send an unhashed code challenge.
            security: Where the resource owner answering is read from.
            logger: Where a request arriving with no resource owner is
                reported, when this deployment logs at all.
        """
        self._server = server
        self._dispatcher = dispatcher
        self._event_factory = event_factory
        self._user_converter = user_converter
        self._client_manager = client_manager
        self._security = security
        self._logger = logger

    async def index_action(
        self,
        request: ServerRequestInterface,
        response: Response,
    ) -> Response:
        """Answer ``request`` with a redirect carrying what the flow issued, or a refusal."""
        try:
            authorization_request = await self._server.validate_authorization_request(request)
            await self._refuse_plain_pkce_unless_allowed(authorization_request)
            answered = await self._resolve(request, authorization_request, response)
        except OAuthServerError as error:
            # A flow answering in the fragment has to be refused in the
            # fragment too, or the refusal lands in a query the client never
            # reads.
            redirect_uri = error.get_redirect_uri() or ""

            return served(
                error.generate_http_response(response, use_fragment="#" in redirect_uri),
            )

        return answered

    async def _resolve(
        self,
        request: ServerRequestInterface,
        authorization_request: AuthorizationRequestInterface,
        response: Response,
    ) -> Response:
        """Ask the deployment about ``authorization_request``, and answer accordingly.

        Raises:
            OAuthServerError: ``access_denied`` when nobody is authenticated on
                the request, so there is no resource owner to ask.
        """
        user = self._security.get_user()
        if user is None:
            self._report_nobody_to_ask(authorization_request)

            raise OAuthServerError.access_denied(
                _NOBODY_TO_ASK,
                _answered_at(authorization_request),
            )
        event = await self._event_factory.from_authorization_request(authorization_request, user)
        _ = await self._dispatcher.dispatch(event, OAuth2Events.AUTHORIZATION_REQUEST_RESOLVE)
        answered = event.get_response()
        if answered is not None:
            # A listener answered the browser itself — the consent page.
            return served(answered)
        _ = authorization_request.set_user(self._user_converter.to_entity(event.get_user()))
        authorization_request.set_authorization_approved(event.get_authorization_resolution())

        return served(
            await self._server.complete_authorization_request(
                request,
                authorization_request,
                response,
            ),
        )

    async def _refuse_plain_pkce_unless_allowed(
        self,
        authorization_request: AuthorizationRequestInterface,
    ) -> None:
        """Refuse an unhashed code challenge unless this client is registered for one.

        The unhashed method puts the verifier in the authorization request,
        where every hop that sees the request sees it — which is the whole
        thing a proof key exists to prevent. It stays available because a
        client on a platform without a hash cannot do better, but only for a
        client whose registration says so.

        Raises:
            OAuthServerError: ``invalid_request`` when the request names the
                unhashed method and the client is not registered for it.
        """
        if authorization_request.get_code_challenge_method() != _PLAIN:
            return
        identifier = authorization_request.get_client().get_identifier()
        client = await self._client_manager.find(identifier)
        # A client the repository validated against but the manager cannot
        # find means the two read different stores; refusing the unhashed
        # method is the safe reading of that, and the consent event reports
        # the disagreement itself.
        if client is None or not client.is_plain_text_pkce_allowed():
            raise OAuthServerError.invalid_request(
                "code_challenge_method",
                "Plain code challenge method is not allowed for this client",
            )

    def _report_nobody_to_ask(
        self,
        authorization_request: AuthorizationRequestInterface,
    ) -> None:
        """Write what the deployment has to do, with the request as data."""
        if self._logger is None:
            return
        self._logger.warning(
            _UNCLAIMED_ENDPOINT,
            {
                "client_id": authorization_request.get_client().get_identifier(),
                "grant_type": authorization_request.get_grant_type_id(),
            },
        )

    @override
    def __repr__(self) -> str:
        """Name the type; what it holds says nothing a reader needs."""
        return f"{type(self).__name__}()"


def _answered_at(authorization_request: AuthorizationRequestInterface) -> str | None:
    """Return where a refusal is delivered, echoing the state the client sent.

    The state goes on the redirect exactly as the grants put it there: a client
    that cannot tie an error back to the request it made cannot tell it from a
    forged one (RFC 6749 §4.1.2.1).
    """
    uri = authorization_request.get_redirect_uri()
    if uri is None:
        return None
    state = authorization_request.get_state()
    if state is None:
        return uri

    return redirect_uri_carrying(uri, {"state": state})
