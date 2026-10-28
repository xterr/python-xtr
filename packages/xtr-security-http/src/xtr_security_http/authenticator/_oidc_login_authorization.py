"""Building the authorization request an OIDC login starts with."""

from __future__ import annotations

import secrets
from base64 import urlsafe_b64encode
from hashlib import sha256
from typing import TYPE_CHECKING, Final, final
from urllib.parse import quote, urlencode

from xtr_security_http.event.oidc_authorization_request_event import (
    OidcAuthorizationRequestEvent,
)

from ._oidc_login_attempts import OidcLoginAttempts
from ._oidc_login_options import OidcLoginOptions, managed_params_of

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_foundation import Session
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

    from xtr_security_http.http_utils import HttpUtils
    from xtr_security_http.oidc.oidc_discovery import OidcDiscovery

__all__ = ["OidcLoginAuthorization"]

_STATE_ENTROPY: Final = 32
"""The random bytes a state is made of, hex-encoded to 64 characters."""
_NONCE_ENTROPY: Final = 32
"""The random bytes a nonce is made of, base64url-encoded to 43 characters
instead of the 64 a hex encoding would take: the nonce travels to the
provider and back inside the ID token, and longer values are known not to be
accepted by every provider."""
_VERIFIER_ENTROPY: Final = 32
"""The random bytes a PKCE code verifier is made of, hex-encoded to the 64
characters RFC 7636, Appendix B recommends."""

_PKCE_S256: Final = "S256"


@final
class OidcLoginAuthorization:
    """Builds the authorization request an OIDC login starts with.

    The one request the entry point answers with: the provider's
    authorization endpoint, carrying the client's identifier, the callback
    the response is to be sent to, the scopes, a state and a nonce of the
    flow's own, and a PKCE challenge — everything the provider echoes back
    or binds to, and nothing the caller configured that the flow does not
    manage itself.
    """

    __slots__ = (
        "_authorization_params",
        "_client_id",
        "_discovery",
        "_event_dispatcher",
        "_http_utils",
        "_options",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the collaborators of the authorization request, each with its own role
        self,
        http_utils: HttpUtils,
        discovery: OidcDiscovery,
        event_dispatcher: EventDispatcherInterface | None,
        options: OidcLoginOptions,
        client_id: str,
        authorization_params: Mapping[str, str],
    ) -> None:
        """Record the URI machinery, the discovery, the dispatcher and the flow's shape."""
        self._http_utils = http_utils
        self._discovery = discovery
        self._event_dispatcher = event_dispatcher
        self._options = options
        self._client_id = client_id
        self._authorization_params = dict(authorization_params)

    async def build(
        self,
        request: ServerRequestInterface,
        session: Session,
        forced_params: Mapping[str, str] | None = None,
    ) -> ResponseInterface:
        """Build and answer the authorization request, storing its attempt in the session.

        The forced parameters are applied after the configured ones and after
        the event, so that neither can drop them: a listener answering with
        "prompt=none", or simply dropping the key, would otherwise turn a
        re-authentication into a silent no-op and leave the user looping
        through the provider.
        """
        attempts = OidcLoginAttempts(session, self._options.firewall_name)
        # Both resolved before anything is stored in the session, so that a
        # provider announcing no usable authorization endpoint does not leave
        # any attempt behind.
        authorization_endpoint = await self._discovery.get_secure_endpoint("authorization_endpoint")
        redirect_uri = self._http_utils.generate_uri(self._options.check_path)

        state = secrets.token_hex(_STATE_ENTROPY)
        nonce = urlsafe_b64encode(secrets.token_bytes(_NONCE_ENTROPY)).rstrip(b"=").decode()
        params: dict[str, str] = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self._options.scopes()),
            "state": state,
            "nonce": nonce,
        }
        code_verifier: str | None = None
        if self._options.pkce_enabled:
            code_verifier = secrets.token_hex(_VERIFIER_ENTROPY)
            params["code_challenge"] = self._derive_code_challenge(code_verifier)
            params["code_challenge_method"] = self._options.pkce_method
        if self._options.max_age is not None:
            params["max_age"] = str(self._options.max_age)

        extra_params = dict(self._authorization_params)
        if self._event_dispatcher is not None:
            event = OidcAuthorizationRequestEvent(
                request,
                self._options.firewall_name,
                extra_params,
            )
            _ = await self._event_dispatcher.dispatch(event)
            extra_params = event.get_params()
            _ = managed_params_of(extra_params)
        params.update(extra_params)
        params.update(forced_params or {})

        await attempts.add(state, nonce, code_verifier, redirect_uri)

        separator = "&" if "?" in authorization_endpoint else "?"
        authorization_url = authorization_endpoint + separator + urlencode(params, quote_via=quote)
        return self._http_utils.create_redirect_response(request, authorization_url)

    def _derive_code_challenge(self, code_verifier: str) -> str:
        """Derive the PKCE code challenge from the verifier, per the configured method.

        "S256" is BASE64URL(SHA256(verifier)) without padding, per RFC 7636,
        Section 4.2; "plain" is the verifier as it is.
        """
        if self._options.pkce_method != _PKCE_S256:
            return code_verifier
        return urlsafe_b64encode(sha256(code_verifier.encode()).digest()).rstrip(b"=").decode()
