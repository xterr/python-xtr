"""The redirect flow of a deployment running the add-on."""

from __future__ import annotations

from datetime import (  # noqa: TC003 -- container hydrates this constructor at runtime
    timedelta,
)
from typing import TYPE_CHECKING, Final, final

# Every name the constructor below reads is imported at runtime: the container
# evaluates those annotations when it hydrates this grant.
from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server_core.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,
)
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,
)

from .authorization_request import NonceAuthorizationRequest
from .response_type import NonceTokenResponse

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_oauth2_server_core.entities.auth_code_entity_interface import (
        AuthCodeEntityInterface,
    )
    from xtr_security_oauth2_server_core.request_types.authorization_request_interface import (
        AuthorizationRequestInterface,
    )
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

__all__ = ["NONCE_PARAMETER", "NonceAuthCodeGrant"]

#: The parameter the add-on reads off the authorization request, carries in the
#: code, and reads back at the token endpoint.
NONCE_PARAMETER: Final[str] = "nonce"


@final
class NonceAuthCodeGrant(AuthCodeGrant):
    """The shipped redirect flow, carrying one more parameter end to end.

    Everything the shipped grant does, plus one parameter of the original
    authorization request remembered across consent, sealed into the code, and
    handed to the answer when the code is redeemed. Nothing of the grant is
    copied: the seams it reaches through are the request it records into, the
    payload the code carries and the answer it hands back.

    A tagged grant is given none of the settings the bundle hands a shipped
    one, so the lifetimes and the proof-key requirement arrive as constructor
    arguments the add-on's bundle read off this deployment's own configuration.
    """

    def __init__(  # noqa: PLR0917 -- one flow built from what the deployment configured
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        auth_code_repository: AuthCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        auth_code_ttl: timedelta,
        refresh_token_ttl: timedelta,
        require_code_challenge: bool,
    ) -> None:
        """Build the flow with the lifetimes and the requirement the deployment set."""
        super().__init__(
            dispatcher,
            clock,
            auth_code_repository,
            refresh_token_repository,
            auth_code_ttl,
        )
        self.set_refresh_token_ttl(refresh_token_ttl)
        if not require_code_challenge:
            self.disable_require_code_challenge_for_public_clients()

    @override
    def create_authorization_request(self) -> AuthorizationRequestInterface:
        """Record what is read into a request that can carry the add-on's parameter."""
        return NonceAuthorizationRequest()

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read the shipped request, and remember the parameter the add-on carries."""
        authorization_request = await super().validate_authorization_request(request)
        carried = self.get_query_string_parameter(NONCE_PARAMETER, request)
        if carried is not None and isinstance(authorization_request, NonceAuthorizationRequest):
            authorization_request.set_nonce(carried)

        return authorization_request

    @override
    def get_auth_code_payload(
        self,
        auth_code: AuthCodeEntityInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> dict[str, object]:
        """Seal the add-on's parameter into the code, beside everything the flow seals."""
        payload = super().get_auth_code_payload(auth_code, authorization_request)
        if isinstance(authorization_request, NonceAuthorizationRequest):
            payload[NONCE_PARAMETER] = authorization_request.get_nonce()

        return payload

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Redeem the code as the shipped grant does, then hand the answer what it carried.

        Read back after the shipped half rather than before it: a code that is
        unreadable, expired, already spent or another client's is refused
        there, in the words the protocol defines, and nothing is read out of it
        here at all.
        """
        answered = await super().respond_to_access_token_request(
            request,
            response_type,
            access_token_ttl,
        )
        if isinstance(answered, NonceTokenResponse):
            answered.set_nonce(self._carried_nonce(request))

        return answered

    def _carried_nonce(self, request: ServerRequestInterface) -> str | None:
        """Return the parameter the code in ``request`` carried, or ``None`` for none.

        Only ever reached once the shipped half has read the same code, so the
        code is known to be readable and to have been redeemable.
        """
        sealed = self.get_request_parameter("code", request)
        carried = None if sealed is None else self.decrypt(sealed).get(NONCE_PARAMETER)

        return carried if isinstance(carried, str) else None
