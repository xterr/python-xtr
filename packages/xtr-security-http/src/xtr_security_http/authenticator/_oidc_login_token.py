"""Stamping a post-authentication token with the OIDC login's tokens and proofs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast

from xtr_security_core.authentication.authentication_method import AuthenticationMethod

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from xtr_security_http.authenticator.passport.passport import Passport
    from xtr_security_http.authenticator.token.post_authentication_token import (
        PostAuthenticationToken,
    )

__all__ = ["stamp_oidc_token"]

_TOKEN_DATA_ATTRIBUTE: Final = "oidc_token_data"  # noqa: S105 -- an attribute name, not a credential
"""Where the authenticator parks the token endpoint response on the passport."""
_AUTH_TIME_ATTRIBUTE: Final = "oidc_auth_time"
_AMR_ATTRIBUTE: Final = "oidc_amr"
_ACR_ATTRIBUTE: Final = "oidc_acr"
_SID_ATTRIBUTE: Final = "oidc_sid"
_ID_TOKEN_ATTRIBUTE: Final = "oidc_id_token"  # noqa: S105 -- an attribute name, not a credential
_ACCESS_TOKEN_ATTRIBUTE: Final = "oidc_access_token"  # noqa: S105 -- an attribute name, not a credential
_REFRESH_TOKEN_ATTRIBUTE: Final = "oidc_refresh_token"  # noqa: S105 -- an attribute name, not a credential
_EXPIRES_AT_ATTRIBUTE: Final = "oidc_access_token_expires_at"


def stamp_oidc_token(
    token: PostAuthenticationToken,
    passport: Passport,
    clock: ClockInterface,
) -> None:
    """Carry the OIDC login's tokens and proofs from the passport onto the token.

    The refresh token and the access token's expiry are both absent unless
    the provider issued them: a provider only issues a refresh token when it
    was asked for one, and "expires_in" is optional.

    A provider whose clock runs ahead would otherwise extend the window the
    recency checks grant, so an "auth_time" from the future never dates the
    proofs past the present.
    """
    token_data = passport.get_attribute(_TOKEN_DATA_ATTRIBUTE)
    now = int(clock.now().timestamp())
    if isinstance(token_data, dict):
        data = cast("dict[str, object]", token_data)
        token.set_attribute(_ID_TOKEN_ATTRIBUTE, data.get("id_token"))
        token.set_attribute(_ACCESS_TOKEN_ATTRIBUTE, data.get("access_token"))
        token.set_attribute(_REFRESH_TOKEN_ATTRIBUTE, data.get("refresh_token"))
        expires_in = data.get("expires_in")
        token.set_attribute(
            _EXPIRES_AT_ATTRIBUTE,
            now + int(expires_in)
            if isinstance(expires_in, (int, float)) and not isinstance(expires_in, bool)
            else None,
        )
    token.set_attribute(_ACR_ATTRIBUTE, passport.get_attribute(_ACR_ATTRIBUTE))
    token.set_attribute(_SID_ATTRIBUTE, passport.get_attribute(_SID_ATTRIBUTE))

    methods = passport.get_attribute(_AMR_ATTRIBUTE)
    methods = (
        [method for method in cast("list[object]", methods) if isinstance(method, str)]
        if isinstance(methods, list)
        else []
    )
    if not methods:
        methods = [AuthenticationMethod.UNSPECIFIED]

    auth_time = passport.get_attribute(_AUTH_TIME_ATTRIBUTE)
    if isinstance(auth_time, int) and not isinstance(auth_time, bool):
        # "auth_time" tells when the user actually authenticated at the
        # provider, which a silent SSO login can place well in the past; it
        # is only validated when "max_age" is requested, so anything
        # non-numeric was discarded rather than trusted.
        token.set_authentication_proofs(dict.fromkeys(methods, min(auth_time, now)))
    elif methods != [AuthenticationMethod.UNSPECIFIED]:
        # Without "auth_time" the login instant is all that is known about
        # when, which is what the proofs listener would record; the methods
        # are still worth keeping.
        token.set_authentication_proofs(dict.fromkeys(methods, now))
