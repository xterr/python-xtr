"""The authorization code flow that carries a sign-in through the code."""

from __future__ import annotations

import re

# Every name the constructor below reads is imported at runtime: the container
# evaluates those annotations when it builds this grant.
from datetime import timedelta  # noqa: TC003 -- read by the container at runtime
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import ClockInterface  # noqa: TC002 -- read by the container at runtime
from xtr_event_dispatcher_contracts import (
    EventDispatcherInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_oauth2_server_core.exception.oauth_server_error import OAuthServerError
from xtr_security_oauth2_server_core.grant.auth_code_grant import AuthCodeGrant
from xtr_security_oauth2_server_core.repositories.auth_code_repository_interface import (
    AuthCodeRepositoryInterface,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_oauth2_server_core.repositories.refresh_token_repository_interface import (
    RefreshTokenRepositoryInterface,  # noqa: TC002 -- read by the container at runtime
)

from xtr_security_openid_connect_server.prompt import parse_prompt
from xtr_security_openid_connect_server.request_types.open_id_authorization_request import (
    OpenIdAuthorizationRequest,
)
from xtr_security_openid_connect_server.response_types.id_token_response import IdTokenResponse

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

__all__ = ["OpenIdAuthCodeGrant"]

#: The names the sign-in is sealed into the code under, beside the flow's own.
_NONCE: Final[str] = "nonce"
_AUTH_TIME: Final[str] = "auth_time"

#: The scope a client asks for to sign the end-user in, rather than only to act for them.
_OPENID_SCOPE: Final[str] = "openid"

#: What a ``max_age`` may look like: digits only, so no sign, no space and no
#: fraction is ever read as an age.
_WHOLE_SECONDS: Final[re.Pattern[str]] = re.compile(r"[0-9]+")

_MAX_AGE_HINT: Final = (
    "Check the `max_age` parameter: it is a whole number of seconds, zero or more"
)
_REDIRECT_URI_HINT: Final = (
    "Check the `redirect_uri` parameter: a request asking for the `openid` scope must name "
    "where it is answered"
)


@final
class OpenIdAuthCodeGrant(AuthCodeGrant):
    """The authorization server's code flow, carrying a sign-in end to end.

    Everything the shipped flow does, plus what a sign-in needs to remember
    across consent and the redirect: the ``nonce`` the client sent, the
    ``prompt`` and ``max_age`` it asked to be signed in with, and when the
    end-user last signed in. The ``nonce`` and the sign-in time are sealed into
    the code beside what the flow seals, and handed to the token answer when
    the code is redeemed, so the ID token can state them.

    The token answer must be able to carry an ID token. One that cannot means
    the server was configured with another answer, which is this server's
    mistake rather than the client's, and is reported as one instead of
    handing out an answer silently missing the ID token the client asked for.

    The lifetimes and the proof-key requirement arrive as constructor
    arguments, because a grant the server is handed whole is given none of the
    settings it hands the grants it builds itself.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- one flow built from what the deployment configured
        self,
        dispatcher: EventDispatcherInterface,
        clock: ClockInterface,
        auth_code_repository: AuthCodeRepositoryInterface,
        refresh_token_repository: RefreshTokenRepositoryInterface,
        auth_code_ttl: timedelta,
        refresh_token_ttl: timedelta,
        require_code_challenge: bool,
    ) -> None:
        """Build the flow with the lifetimes and the proof-key requirement configured.

        Args:
            dispatcher: Where the flow announces what it issued.
            clock: What the codes and tokens are timed against.
            auth_code_repository: Where codes are minted and spent.
            refresh_token_repository: Where refresh tokens are minted.
            auth_code_ttl: How long a code may wait to be redeemed.
            refresh_token_ttl: How long a refresh token lasts.
            require_code_challenge: Whether a public client must send a proof
                key.
        """
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
        """Record what is read into a request that can carry a sign-in."""
        return OpenIdAuthorizationRequest()

    @override
    async def validate_authorization_request(
        self,
        request: ServerRequestInterface,
    ) -> AuthorizationRequestInterface:
        """Read the shipped request, and what the sign-in asks of it.

        The shipped half is read first, so a request from an unknown client or
        for an unregistered redirect is refused as the flow always refused it,
        before anything of the sign-in is looked at.

        A sign-in must name the redirect URI it is answered at, although the
        shipped flow lets a client registered with a single URI leave it out,
        as a request not asking for ``openid`` still may. A sign-in leaving it
        out is refused as a document rather than a redirect: it named nowhere
        to send the refusal.

        Raises:
            OAuthServerError: Whatever the shipped flow refuses with, and
                ``invalid_request`` when a request asking for ``openid`` names
                no ``redirect_uri``, ``prompt`` names a value this server does
                not act on or ``none`` beside another, or ``max_age`` is not a
                whole number of seconds.
        """
        authorization_request = await super().validate_authorization_request(request)
        named = self.get_query_string_parameter("redirect_uri", request)
        scopes = authorization_request.get_scopes()
        if named is None and any(scope.get_identifier() == _OPENID_SCOPE for scope in scopes):
            raise OAuthServerError.invalid_request("redirect_uri", _REDIRECT_URI_HINT)
        prompt = parse_prompt(self.get_query_string_parameter("prompt", request))
        max_age = _max_age(self.get_query_string_parameter("max_age", request))
        if isinstance(authorization_request, OpenIdAuthorizationRequest):
            authorization_request.set_nonce(self.get_query_string_parameter(_NONCE, request))
            authorization_request.set_prompt(prompt)
            authorization_request.set_max_age(max_age)

        return authorization_request

    @override
    def get_auth_code_payload(
        self,
        auth_code: AuthCodeEntityInterface,
        authorization_request: AuthorizationRequestInterface,
    ) -> dict[str, object]:
        """Seal the ``nonce`` and the sign-in time into the code, when there are any."""
        payload = super().get_auth_code_payload(auth_code, authorization_request)
        if isinstance(authorization_request, OpenIdAuthorizationRequest):
            nonce = authorization_request.get_nonce()
            if nonce is not None:
                payload[_NONCE] = nonce
            auth_time = authorization_request.get_auth_time()
            if auth_time is not None:
                payload[_AUTH_TIME] = auth_time

        return payload

    @override
    async def respond_to_access_token_request(
        self,
        request: ServerRequestInterface,
        response_type: ResponseTypeInterface,
        access_token_ttl: timedelta,
    ) -> ResponseTypeInterface:
        """Redeem the code as the shipped flow does, then hand the answer the sign-in.

        The sign-in is read back after the shipped half rather than before it:
        a code that is unreadable, expired, already spent or another client's
        is refused there, in the words the protocol defines, and nothing is
        read out of it here at all.

        Raises:
            OAuthServerError: Whatever the shipped flow refuses with, and
                ``server_error`` when the token answer cannot carry an ID
                token, which names the setting that chose it.
        """
        answered = await super().respond_to_access_token_request(
            request,
            response_type,
            access_token_ttl,
        )
        if not isinstance(answered, IdTokenResponse):
            raise OAuthServerError.server_error(
                f"the token answer is a {type(answered).__name__}, which cannot carry an ID "
                "token; set `authorization_server.response_type_class` to IdTokenResponse or "
                "a subclass of it.",
            )
        sealed = self.get_request_parameter("code", request)
        payload = {} if sealed is None else self.decrypt(sealed)
        subject = self._payload_text(payload, "user_id")
        client_id = self._payload_text(payload, "client_id")
        if subject is not None and client_id is not None:
            answered.set_identity(
                subject,
                client_id,
                self._payload_whole_number(payload, _AUTH_TIME),
                self._payload_text(payload, _NONCE),
            )

        return answered


def _max_age(max_age: str | None) -> int | None:
    """Read ``max_age`` as the number of seconds it names, ``None`` when absent.

    Refused here rather than handed on: a negative or malformed age is the
    client's mistake, answered as one, while the request refuses a negative
    age it is handed as a mistake in this server's own code.

    Raises:
        OAuthServerError: ``invalid_request`` when ``max_age`` is not a whole
            number of seconds, zero or more.
    """
    if max_age is None:
        return None
    if _WHOLE_SECONDS.fullmatch(max_age) is None:
        raise OAuthServerError.invalid_request("max_age", _MAX_AGE_HINT)

    return int(max_age)
