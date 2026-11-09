"""The chain step deciding, at the authorization endpoint, whether the end-user signs in again."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final
from urllib.parse import parse_qsl, urlencode

from typing_extensions import override

# Every name the constructor below reads is imported at runtime: the container
# evaluates those annotations when it builds this step.
from xtr_clock import ClockInterface, SystemClock
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import (
    StarletteHttpFactoryInterface,
)
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_core.authentication.token.storage.token_storage_interface import (
    TokenStorageInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_http import SecurityRequestAttributes, parked_session_of
from xtr_security_http.firewall import AbstractListener
from xtr_security_http.http_utils import (
    HttpUtils,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_http.util.target_path import save_target_path
from xtr_security_oauth2_server.posted_form_as_query import posted_form_as_query
from xtr_security_oauth2_server_core.authorization_server import (
    AuthorizationServer,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError

from xtr_security_openid_connect_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_openid_connect_server.prompt import login_required
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["OpenIdPromptListener"]

#: Where the step runs in the chain: after the steps that restore and
#: establish the token, at ``0``, and before access control, at ``-255``, which
#: would send an anonymous request to the login page before ``prompt=none``
#: could be answered.
_PROMPT_PRIORITY: Final = -200

#: The parameters this step decides on; a request carrying neither is left to
#: the authorization endpoint.
_DECIDED_BY: Final[frozenset[str]] = frozenset({"prompt", "max_age"})

_PROMPT: Final = "prompt"
_NONE: Final = "none"
_LOGIN: Final = "login"

#: Where the two settings the refusal below names are written.
_SECURITY_CONFIG_FILE: Final = "<app>/config/packages/security.py"
_CONFIG_FILE: Final = "<app>/config/packages/openid_connect_server.py"


@final
class OpenIdPromptListener(AbstractListener):
    """Decides whether a sign-in asked for may go on as the end-user stands.

    A step of the login firewall's chain, on the authorization endpoint. A
    client may ask that the end-user be shown nothing (``prompt=none``), that
    they sign in again (``prompt=login``), or that their sign-in be no older
    than ``max_age`` seconds. Each is decided here, before the endpoint runs:
    the endpoint refuses a request nobody is signed in on, which is exactly the
    request ``prompt=none`` has to be answered for.

    ``prompt=none`` with nobody signed in, or with a sign-in too old, is
    refused with ``login_required``, delivered to the client. A sign-in that
    has to be made again sends the end-user to the login page, keeping the
    request in their session to return to — with ``login`` taken out of
    ``prompt``, so the return trip goes on to the code instead of asking again.
    A request the authorization server refuses outright is answered as the
    endpoint answers it: at the redirect URI only when it was validated, as a
    plain document otherwise.

    A request posted as a form is read as the endpoint reads it, its form as
    its query, so ``prompt`` and ``max_age`` are decided whichever way the
    request came, and the request kept to return to is the one the form
    carried, as the ``GET`` the return trip makes.

    The request is kept in the session of the login firewall, so that firewall
    must keep one; a stateless one is refused, by name, when a re-login is
    first asked of it.
    """

    __slots__ = (
        "_authorization_server",
        "_authorize_path",
        "_bridge",
        "_clock",
        "_http_utils",
        "_login_firewall",
        "_login_path",
        "_response_factory",
        "_token_storage",
    )

    def __init__(  # noqa: PLR0913 -- one step built from the parts it answers through and three settings
        self,
        token_storage: TokenStorageInterface,
        authorization_server: AuthorizationServer,
        http_utils: HttpUtils,
        response_factory: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
        *,
        login_path: str,
        login_firewall: str,
        authorize_path: str,
        clock: ClockInterface | None = None,
    ) -> None:
        """Build the step over the request's token and the authorization server.

        Args:
            token_storage: The request's token storage, holding who is signed
                in once the chain's earlier steps have run.
            authorization_server: Reads the authorization request, refusing
                it as the authorization endpoint would.
            http_utils: Matches the request's path and builds the redirect to
                the login page.
            response_factory: Builds the response a refusal is written on.
            bridge: Turns a message response into one the lifecycle's event
                accepts.
            login_path: Where an end-user asked to sign in again is sent.
            login_firewall: The firewall signing them in there, whose session
                keeps the request to return to.
            authorize_path: Where the authorization endpoint is served.
            clock: What a sign-in's age is measured against; the system clock
                when left out.
        """
        self._token_storage = token_storage
        self._authorization_server = authorization_server
        self._http_utils = http_utils
        self._response_factory = response_factory
        self._bridge = bridge
        self._login_path = login_path
        self._login_firewall = login_firewall
        self._authorize_path = authorize_path
        self._clock: ClockInterface = SystemClock() if clock is None else clock

    @override
    async def supports(self, request: ServerRequestInterface) -> bool:
        """Answer whether ``request`` is for the authorization endpoint."""
        return self._http_utils.check_request_path(request, self._authorize_path)

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Let the request go on, refuse it, or send the end-user to sign in again.

        Raises:
            InvalidConfigurationError: When a re-login is needed and the login
                firewall keeps no session to return from it with.
        """
        try:
            request = await posted_form_as_query(request_event.request)
            query = parse_qsl(request.get_uri().get_query(), keep_blank_values=True)
            if not any(name in _DECIDED_BY for name, _ in query):
                return
            authorization_request = await self._authorization_server.validate_authorization_request(
                request
            )
            if isinstance(authorization_request, OpenIdAuthorizationRequest):
                await self._decide(request_event, authorization_request, query)
        except OAuthServerError as error:
            await self._answer(request_event, await self._refusal(error))

    async def _decide(
        self,
        request_event: RequestEvent,
        authorization_request: OpenIdAuthorizationRequest,
        query: list[tuple[str, str]],
    ) -> None:
        """Act on what ``authorization_request`` asks of the end-user's sign-in.

        Raises:
            OAuthServerError: ``login_required`` for ``prompt=none`` when the
                end-user would have to sign in.
        """
        prompt = authorization_request.get_prompt()
        fresh = self._is_fresh(self._token_storage.get_token(), authorization_request.get_max_age())
        if _NONE in prompt:
            if not fresh:
                raise login_required(
                    authorization_request.get_redirect_uri(),
                    authorization_request.get_state(),
                )
            return
        if _LOGIN in prompt or not fresh:
            await self._send_to_login(request_event, query, prompt)

    def _is_fresh(self, token: TokenInterface | None, max_age: int | None) -> bool:
        """Tell whether someone is signed in, recently enough for ``max_age``.

        The newest proof on the token is when they last signed in. A token
        proving nothing — a remembered login — has no known sign-in time, so
        it is never recent enough for a ``max_age``.
        """
        if token is None or token.get_user() is None:
            return False
        if max_age is None:
            return True
        signed_in_at = max(token.get_authentication_proofs().values(), default=None)
        if signed_in_at is None:
            return False

        return int(self._clock.now().timestamp()) - signed_in_at <= max_age

    async def _send_to_login(
        self,
        request_event: RequestEvent,
        query: list[tuple[str, str]],
        prompt: frozenset[str],
    ) -> None:
        """Keep the request to return to, without ``login``, and send the end-user to sign in.

        Only the request ``supports`` is handed carries the request's state
        bag; the session the chain parked is reached through it.

        Raises:
            InvalidConfigurationError: When the request has no session parked,
                because the login firewall is stateless.
        """
        request = request_event.request
        session = parked_session_of(
            request.with_attribute(SecurityRequestAttributes.STATE_BAG, request_event.state),
        )
        if session is None:
            raise InvalidConfigurationError(
                f'The firewall "{self._login_firewall}" keeps no session, so the authorization '
                "request has nowhere to wait while the end-user signs in again. Set "
                f"stateless=False on it in {_SECURITY_CONFIG_FILE}, or name the stateful "
                f"firewall signing end-users in at {self._login_path} in login_firewall in "
                f"{_CONFIG_FILE}.",
            )
        kept = [(name, value) for name, value in query if name != _PROMPT]
        remaining = prompt - {_LOGIN}
        if remaining:
            kept.append((_PROMPT, " ".join(sorted(remaining))))
        target = f"{request.get_uri().get_path()}?{urlencode(kept)}"
        await save_target_path(session, self._login_firewall, target)
        await self._answer(
            request_event,
            self._http_utils.create_redirect_response(request, self._login_path),
        )

    async def _refusal(self, error: OAuthServerError) -> ResponseInterface:
        """Return ``error`` answered as the authorization endpoint answers a refusal."""
        redirect_uri = error.get_redirect_uri() or ""

        return await error.generate_http_response(
            self._response_factory.create_response(),
            use_fragment="#" in redirect_uri,
        )

    async def _answer(self, request_event: RequestEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``request_event`` as what the lifecycle can send.

        The kernel's own response is set as it is; a pure message is converted
        through the bridge first.
        """
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the step's position: after the token is known, before access control."""
        return _PROMPT_PRIORITY

    @override
    def __repr__(self) -> str:
        """Name the type; what it holds says nothing a reader needs."""
        return f"{type(self).__name__}()"
