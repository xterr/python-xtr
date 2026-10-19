"""Renewing the OIDC tokens a security token carries."""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, final

from xtr_clock import SystemClock
from xtr_security_core.exception import AuthenticationError

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .oidc_client_interface import OidcClientInterface
    from .oidc_discovery import OidcDiscovery
    from .oidc_id_token import OidcIdToken
    from .oidc_signature_verifier import OidcSignatureVerifier

__all__ = ["OidcTokenRefresher"]

_REFRESH_TOKEN_ATTRIBUTE: str = "oidc_refresh_token"  # noqa: S105 -- an attribute name, not a credential
"""Where the firewall keeps the refresh token the provider issued."""
_ACCESS_TOKEN_ATTRIBUTE: str = "oidc_access_token"  # noqa: S105 -- an attribute name, not a credential
"""Where the firewall keeps the access token the provider issued."""
_EXPIRES_AT_ATTRIBUTE: str = "oidc_access_token_expires_at"
"""Where the firewall keeps the moment the access token expires at."""
_ID_TOKEN_ATTRIBUTE: str = "oidc_id_token"  # noqa: S105 -- an attribute name, not a credential
"""Where the firewall keeps the ID token the provider issued."""
_SID_ATTRIBUTE: str = "oidc_sid"
"""Where the firewall keeps the session the provider names, when it does."""


@final
class OidcTokenRefresher:
    """Renews the OIDC tokens a security token carries.

    The renewal goes through the refresh token grant of RFC 6749, Section 6.
    The tokens the ``oidc_login`` authenticator obtained are held as
    attributes of the security token, which the firewall keeps in the
    session: renewing them in place is what keeps the access token usable to
    call an API on behalf of the logged-in user, long after the short
    lifetime the provider gave it.
    """

    __slots__ = (
        "_client",
        "_client_id",
        "_clock",
        "_discovery",
        "_id_token",
        "_leeway",
        "_signature_verifier",
    )

    def __init__(  # noqa: PLR0913, PLR0917 -- the upstream wiring shape: the client, the discovery, the ID token reader, the registration and the three knobs
        self,
        client: OidcClientInterface,
        discovery: OidcDiscovery,
        id_token: OidcIdToken,
        client_id: str,
        signature_verifier: OidcSignatureVerifier | None = None,
        leeway: int = 30,
        clock: ClockInterface | None = None,
    ) -> None:
        """Record the client, the discovery, the ID token reader and the renewal knobs.

        Args:
            client: Makes the refresh token grant.
            discovery: Reads the issuer the refreshed ID token is validated
                against.
            id_token: Decodes and validates the refreshed ID token.
            client_id: The client the tokens were issued to, checked as the
                audience of a refreshed ID token.
            signature_verifier: Verifies the signature of a refreshed ID
                token against the provider JWKS, or ``None`` to decode it
                without verifying it.
            leeway: How many seconds before its expiry the access token is
                renewed, so that one handed to a downstream call does not
                expire in flight.
            clock: What the expiry is read and written against.
        """
        self._client = client
        self._discovery = discovery
        self._id_token = id_token
        self._client_id = client_id
        self._signature_verifier = signature_verifier
        self._leeway = leeway
        self._clock = clock if clock is not None else SystemClock()

    async def refresh_if_needed(self, token: TokenInterface) -> bool:
        """Renew the access token when it is about to expire, and report whether it was.

        Nothing happens when the security token carries no refresh token, or
        when the token endpoint reported no ``expires_in``, as nothing then
        says the access token went stale.

        Returns:
            Whether the tokens were renewed.

        Raises:
            OidcInvalidGrantError: When the provider no longer honors the
                refresh token.
            AuthenticationError: When the renewal fails for any other reason.
        """
        refresh_token = _attribute(token, _REFRESH_TOKEN_ATTRIBUTE)
        expires_at = _attribute(token, _EXPIRES_AT_ATTRIBUTE)
        if not isinstance(refresh_token, str) or not refresh_token:
            return False
        if isinstance(expires_at, bool) or not isinstance(expires_at, (int, float)):
            return False
        if int(self._clock.now().timestamp()) + self._leeway < int(expires_at):
            return False
        await self.refresh(token)
        return True

    async def refresh(self, token: TokenInterface) -> None:
        """Renew the access token, whatever its expiry, and store the new tokens.

        The security token receives the access token and its expiry, the
        refresh token when the provider rotated it, and the ID token and its
        ``sid`` when it issued a new one.

        Raises:
            OidcInvalidGrantError: When the provider no longer honors the
                refresh token.
            AuthenticationError: When the renewal fails for any other reason.
        """
        refresh_token = _attribute(token, _REFRESH_TOKEN_ATTRIBUTE)
        if not isinstance(refresh_token, str) or not refresh_token:
            raise AuthenticationError(
                "The security token carries no OIDC refresh token: the access token "
                "cannot be renewed.",
            )
        token_data = await self._client.refresh_token(refresh_token)
        access_token = token_data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise AuthenticationError(
                'The token endpoint response does not contain a valid "access_token".',
            )
        # The whole response is validated before anything is stored, so that a
        # rejected ID token leaves the security token exactly as it was.
        if "id_token" in token_data:
            id_token_value = token_data["id_token"]
            claims = await self._verify_refreshed_id_token(token, id_token_value)
            token.set_attribute(_ID_TOKEN_ATTRIBUTE, id_token_value)
            sid = claims.get("sid")
            if isinstance(sid, str) and sid:
                token.set_attribute(_SID_ATTRIBUTE, sid)
        token.set_attribute(_ACCESS_TOKEN_ATTRIBUTE, access_token)
        expires_in = token_data.get("expires_in")
        expires_at: object = (
            int(self._clock.now().timestamp()) + int(expires_in)
            if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool)
            else None
        )
        token.set_attribute(_EXPIRES_AT_ATTRIBUTE, expires_at)
        # RFC 6749, Section 6: issuing a new refresh token is a MAY, and the
        # one just used stays valid until the provider replaces it.
        new_refresh = token_data.get("refresh_token")
        if isinstance(new_refresh, str) and new_refresh:
            token.set_attribute(_REFRESH_TOKEN_ATTRIBUTE, new_refresh)

    async def _verify_refreshed_id_token(
        self,
        token: TokenInterface,
        id_token: object,
    ) -> dict[str, object]:
        """Validate an ID token returned by the refresh token grant.

        The rules are the ones of OIDC Core 1.0, Section 12.2. Neither a
        ``nonce`` nor a ``max_age`` is checked: no authorization request was
        made, and the ``auth_time`` claim still reports the original
        authentication.

        Returns:
            The claims of the refreshed ID token.

        Raises:
            AuthenticationError: When the refreshed ID token does not describe
                the same authentication.
        """
        if not isinstance(id_token, str) or not id_token:
            raise AuthenticationError(
                'The token endpoint response does not contain a valid "id_token".',
            )
        claims = (
            await self._signature_verifier.verify(id_token)
            if self._signature_verifier is not None
            else await self._id_token.decode(id_token)
        )
        issuer = (await self._discovery.get_configuration()).get("issuer")
        self._id_token.validate_claims(
            claims, issuer if isinstance(issuer, str) else "", self._client_id
        )
        previous_id_token = _attribute(token, _ID_TOKEN_ATTRIBUTE)
        if not isinstance(previous_id_token, str) or not previous_id_token:
            raise AuthenticationError(
                "The security token carries no OIDC ID token to compare the refreshed one against.",
            )
        previous_subject = (await self._id_token.decode(previous_id_token)).get("sub")
        subject = claims.get("sub")
        if not isinstance(previous_subject, str) or not isinstance(subject, str):
            raise AuthenticationError(
                'The "sub" claim of the refreshed ID token does not match the one of '
                "the ID token issued at authentication.",
            )
        if not hmac.compare_digest(previous_subject, subject):
            raise AuthenticationError(
                'The "sub" claim of the refreshed ID token does not match the one of '
                "the ID token issued at authentication.",
            )
        return claims


def _attribute(token: TokenInterface, name: str) -> object:
    """Return the attribute ``name`` a token carries, or ``None`` without it."""
    return token.get_attribute(name) if token.has_attribute(name) else None
