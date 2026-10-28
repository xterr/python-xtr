"""The chain step that logs a request out, through the logout event."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_security_core.authentication.token.storage.token_storage_interface import (  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
    TokenStorageInterface,
)
from xtr_security_csrf.csrf_token import CsrfToken

from xtr_security_http._request_parameters import payload_parameter, query_parameter
from xtr_security_http._security_state import security_state_of
from xtr_security_http.event.logout_event import LogoutEvent
from xtr_security_http.exception import LogoutError

from .abstract_listener import AbstractListener

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_csrf.csrf_token_manager_interface import CsrfTokenManagerInterface

    from xtr_security_http.http_utils import HttpUtils

__all__ = ["LogoutListener"]

# Where the logout step runs in the chain: behind the steps that authenticate
# and decide, ahead of the ones that only clean up after a request. The value
# is what the firewall's insertion rule was written around — a logout is
# handled before the steps running at a lower priority, so the token is still
# there for the ones that would read it.
_LOGOUT_PRIORITY: Final = -127


@final
class LogoutListener(AbstractListener):
    """Logs a request out: announces the logout, then clears the token.

    A chain step for a firewall configured with a logout path. ``supports``
    answers whether the request is asking for a logout — its path is the
    configured one — and ``authenticate`` carries the logout out: the request
    proves itself first, when a cross-site request forgery manager is wired,
    then the logout event is announced on the firewall's own dispatcher, where
    the firewall's logout listeners each do their part, and the token is
    cleared from the storage and the request's state. A response one of the
    event's listeners answered with is set on the request's event, which also
    stops the chain.

    The event is announced before the token is cleared, so its listeners read
    the token being logged out; the storage is cleared after, so a listener
    that answers with the token's last sight — a farewell page naming the
    user — still can.
    """

    __slots__ = (
        "_bridge",
        "_csrf_parameter",
        "_csrf_token_id",
        "_csrf_token_manager",
        "_dispatcher",
        "_http_utils",
        "_logout_path",
        "_token_storage",
    )

    def __init__(  # noqa: PLR0913 -- the per-firewall shape: one step built from its firewall's parts
        self,
        token_storage: TokenStorageInterface,
        http_utils: HttpUtils,
        dispatcher: EventDispatcherInterface,
        bridge: StarletteHttpFactoryInterface,
        csrf_token_manager: CsrfTokenManagerInterface | None = None,
        *,
        csrf_parameter: str = "_csrf_token",
        csrf_token_id: str = "logout",  # noqa: S107 -- the default id of the logout's forgery token, not a credential
        logout_path: str = "/logout",
    ) -> None:
        """Build the step over one firewall's logout parts.

        Args:
            token_storage: The request's token storage, cleared by the
                logout.
            http_utils: Matches the request's path against the configured
                logout path.
            dispatcher: The firewall's own dispatcher, where the logout event
                is announced — the same one the firewall's login listeners
                run on, so an application listening there hears a logout too.
            bridge: Turns a logout listener's pure message response into one
                the lifecycle's event accepts.
            csrf_token_manager: Vouches for the token a logout request
                presents, or ``None`` while the firewall asks for no proof —
                the cross-site request forgery protection is optional, the
                way the logout configuration's is.
            csrf_parameter: The name the request carries the forgery token
                under, in its submitted form or its query string.
            csrf_token_id: The id the forgery token is stored under.
            logout_path: The path a request asks for a logout by.
        """
        self._token_storage = token_storage
        self._http_utils = http_utils
        self._dispatcher = dispatcher
        self._bridge = bridge
        self._csrf_token_manager = csrf_token_manager
        self._csrf_parameter = csrf_parameter
        self._csrf_token_id = csrf_token_id
        self._logout_path = logout_path

    @override
    async def supports(self, request: ServerRequestInterface) -> bool:
        """Answer whether ``request`` is asking for a logout.

        A request that is not asking for one — its path is not the
        configured logout path — answers a strict ``False``, so the chain
        skips this step and runs on.
        """
        return self._http_utils.check_request_path(request, self._logout_path)

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Carry the logout out: prove the request, announce it, clear the token.

        Raises:
            LogoutError: When a cross-site request forgery manager is wired
                and the request presented no token value, or one the manager
                does not vouch for.
        """
        request = request_event.request
        await self._prove_the_request(request)
        logout_event = LogoutEvent(request, self._token_storage.get_token())
        _ = await self._dispatcher.dispatch(logout_event)
        self._token_storage.set_token(None)
        security_state_of(request_event.state).token = None
        answered = logout_event.get_response()
        if answered is not None:
            await self._answer(request_event, answered)

    async def _prove_the_request(self, request: ServerRequestInterface) -> None:
        """Check the forgery token a logout request presents, when one is wired.

        The value is read where a submitted form carries it first and the
        query string second, and vouched for by the manager; a request that
        presents no value, or one the manager does not vouch for, is refused
        — a logout is a request that acts on the caller's behalf, so it is
        held to the same proof a form of the application is.
        """
        manager = self._csrf_token_manager
        if manager is None:
            return
        value = payload_parameter(request, self._csrf_parameter)
        if value is None:
            value = query_parameter(request, self._csrf_parameter)
        if not isinstance(value, str) or not await manager.is_token_valid(
            CsrfToken(self._csrf_token_id, value),
        ):
            raise LogoutError("Invalid CSRF token.")

    async def _answer(self, request_event: RequestEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``request_event`` as what the lifecycle can send.

        The kernel's own response is both a message and what the framework
        sends, so it is set as it is; a pure message — one a logout listener
        built through a response factory — is converted through the bridge,
        the kernel's rule for messages from elsewhere.
        """
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))

    @staticmethod
    @override
    def get_priority() -> int:
        """Return the logout step's position in the chain: behind the deciders."""
        return _LOGOUT_PRIORITY
