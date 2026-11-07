"""The chain step starting the client application's sign-in at a path of its own.

A firewall step hands the login's entry point the request carrying the
request's security state, where the session the chain opened is kept. The
login keeps its ``state``, ``nonce`` and proof key in that session, so it is
started from here rather than from a refused page: the request a refusal is
answered for carries no such state, and the login would find no session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Final, final

from typing_extensions import override
from xtr_dependency_injection import Target, as_alias, as_service

# The container reads the constructor's annotations at runtime to build the step.
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_security_http import SecurityRequestAttributes
from xtr_security_http.authenticator.oidc_login_authenticator import OidcLoginAuthenticator
from xtr_security_http.firewall import AbstractListener, FirewallListenerInterface
from xtr_security_http.http_utils import HttpUtils

from .config import FIREWALL, SIGN_IN_STEP

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["SIGN_IN_PATH", "SignInStep"]

#: Where a visitor asks to be signed in.
SIGN_IN_PATH: Final = "/sign-in"

#: After the step that opens the session, at ``0``, before access control.
_PRIORITY: Final = -100


@final
@as_service(lifetime="scoped")
@as_alias(FirewallListenerInterface, qualifier=SIGN_IN_STEP)
class SignInStep(AbstractListener):
    """Sends a visitor of the sign-in path to the provider, through the login itself."""

    __slots__ = ("_authenticator", "_bridge", "_http_utils")

    def __init__(
        self,
        authenticator: Annotated[OidcLoginAuthenticator, Target(FIREWALL)],
        http_utils: HttpUtils,
        bridge: StarletteHttpFactoryInterface,
    ) -> None:
        self._authenticator = authenticator
        self._http_utils = http_utils
        self._bridge = bridge

    @override
    async def supports(self, request: ServerRequestInterface) -> bool:
        return self._http_utils.check_request_path(request, SIGN_IN_PATH)

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        request = request_event.request.with_attribute(
            SecurityRequestAttributes.STATE_BAG,
            request_event.state,
        )
        response = await self._authenticator.start(request)
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))

    @staticmethod
    @override
    def get_priority() -> int:
        return _PRIORITY
