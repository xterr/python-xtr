"""The token answer of a sign-in: the bearer answer plus a signed ID token."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from typing_extensions import override

# The three names the constructor below reads are imported at runtime: the
# container evaluates those annotations when it builds this answer.
from xtr_clock import ClockInterface  # noqa: TC002 -- read by the container at runtime
from xtr_security_oauth2_server_core.entities.access_token_signer import (
    AccessTokenSigner,  # noqa: TC002 -- read by the container at runtime
)
from xtr_security_oauth2_server_core.response_types.bearer_token_response import BearerTokenResponse

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)
from xtr_security_openid_connect_server.id_token_settings import (
    IdTokenSettings,  # noqa: TC001 -- read by the container at runtime
)
from xtr_security_openid_connect_server.token_hash import token_hash

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
        AccessTokenEntityInterface,
    )

__all__ = ["IdTokenResponse"]

#: The scope a client asks for to sign the end-user in, rather than only to act for them.
_OPENID_SCOPE: Final[str] = "openid"

#: What the header says an ID token is: a plain JWT, which a resource server
#: tells apart from an access token's ``at+jwt``.
_TYPE_HEADER: Final[str] = "JWT"


class IdTokenResponse(BearerTokenResponse):
    """The bearer answer, plus the ID token of the sign-in it was earned by.

    Put in place of the shipped answer through the authorization server's
    ``response_type_class``, and built by the container from its constructor.

    The ID token says who signed in, to which client, when, and how long the
    statement holds — nothing else. What the end-user's profile says is
    answered by the userinfo endpoint, to whoever holds the access token, so
    building this answer reads nothing and asks nothing.

    It is signed with the key the access token is signed with, so a client
    verifies both against the one key set the server publishes. Its
    ``at_hash`` is the hash of the access token string the same answer
    carries: the access token signs once, and every reading of it is that one
    string.

    The sign-in is set per request, on the copy of this answer the server
    hands the grant, and is held as plain values only: a shallow copy shares
    whatever its template holds, and one request's sign-in must never reach
    another request's answer.
    """

    def __init__(
        self,
        clock: ClockInterface,
        signer: AccessTokenSigner,
        settings: IdTokenSettings,
    ) -> None:
        """Answer against ``clock``, signing ID tokens with ``signer`` as ``settings`` say."""
        super().__init__(clock)
        self._signer: AccessTokenSigner = signer
        self._settings: IdTokenSettings = settings
        self._subject: str | None = None
        self._client_id: str | None = None
        self._auth_time: int | None = None
        self._nonce: str | None = None

    def set_identity(
        self,
        subject: str,
        client_id: str,
        auth_time: int | None,
        nonce: str | None,
    ) -> None:
        """Carry the sign-in the token was earned by, so the answer can state it.

        Args:
            subject: The identifier of the end-user who signed in.
            client_id: The client the ID token is addressed to.
            auth_time: When the end-user signed in, in seconds since the epoch,
                or ``None`` when that is not known.
            nonce: The ``nonce`` the authorization request carried, or
                ``None`` when it carried none.
        """
        self._subject = subject
        self._client_id = client_id
        self._auth_time = auth_time
        self._nonce = nonce

    @override
    def get_extra_params(self, access_token: AccessTokenEntityInterface) -> Mapping[str, object]:
        """Return the ID token, when the token was earned by a sign-in.

        A sign-in is a grant that handed over who signed in, for a token
        carrying the ``openid`` scope. Anything else — a refresh, a client
        acting for itself, a client that asked only to act for the end-user —
        is answered as the plain bearer answer.

        Raises:
            InvalidArgumentError: When the signature provider answered with a
                token it had not signed.
        """
        if self._subject is None or self._client_id is None:
            return {}
        if all(scope.get_identifier() != _OPENID_SCOPE for scope in access_token.get_scopes()):
            return {}

        return {"id_token": self._id_token(access_token, self._subject, self._client_id)}

    def _id_token(
        self,
        access_token: AccessTokenEntityInterface,
        subject: str,
        client_id: str,
    ) -> str:
        """Sign the ID token stating the sign-in, beside ``access_token``."""
        issued_at = int(self._clock.now().timestamp())
        ttl = self._settings.ttl
        expires_at = (
            int(access_token.get_expiry_date_time().timestamp())
            if ttl is None
            else issued_at + int(ttl.total_seconds())
        )
        claims: dict[str, object] = {
            "iss": self._signer.issuer,
            "sub": subject,
            "aud": client_id,
            "exp": expires_at,
            "iat": issued_at,
        }
        if self._auth_time is not None:
            claims["auth_time"] = self._auth_time
        if self._nonce is not None:
            claims["nonce"] = self._nonce
        claims["at_hash"] = token_hash(
            access_token.to_string(),
            self._settings.algorithm,
            self._settings.curve,
        )
        created = self._signer.jws_provider.create(
            claims,
            {"typ": _TYPE_HEADER, "kid": self._signer.key_id},
        )
        if not created.is_signed():
            raise InvalidArgumentError(
                "The signature provider answered with an unsigned ID token, which no client "
                "may be handed; check the provider's algorithm and key.",
            )
        return created.get_token()
