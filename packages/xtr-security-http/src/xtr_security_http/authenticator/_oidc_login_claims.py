"""The user claims an OIDC login reads, the binding to the ID token, and the passport."""

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Final, cast

from xtr_security_core.exception import AuthenticationError

from xtr_security_http.authenticator.passport.badge.user_badge import UserBadge
from xtr_security_http.authenticator.passport.self_validating_passport import (
    SelfValidatingPassport,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_security_core.user.user_provider_interface import UserProviderInterface

    from xtr_security_http.oidc.oidc_client_interface import OidcClientInterface

    from ._oidc_login_options import OidcLoginOptions

__all__ = ["build_passport", "fetch_user_claims"]

_USER_INFO_SOURCE: Final = "userinfo"
"""The one source that fetches the claims over the network; the other reads them
off the validated ID token."""

_TOKEN_DATA_ATTRIBUTE: Final = "oidc_token_data"  # noqa: S105 -- an attribute name, not a credential
_AUTH_TIME_ATTRIBUTE: Final = "oidc_auth_time"
_AMR_ATTRIBUTE: Final = "oidc_amr"
_ACR_ATTRIBUTE: Final = "oidc_acr"
_SID_ATTRIBUTE: Final = "oidc_sid"


async def fetch_user_claims(
    client: OidcClientInterface,
    access_token: str,
    id_token_claims: Mapping[str, object],
    options: OidcLoginOptions,
) -> dict[str, object]:
    """Read the user claims from the source the options name, and check the identifier claim.

    The source is the userinfo endpoint or the validated ID token. Claims
    fetched from the userinfo endpoint are tied to the authenticated user by
    the OIDC Core 1.0, Section 5.3.2 rule that its "sub" matches the ID
    token's — which the caller has already had validated.

    Raises:
        AuthenticationError: When the configured identifier claim is missing
            or invalid, or when the userinfo "sub" does not match the ID
            token's.
    """
    from_user_info = options.user_data_source == _USER_INFO_SOURCE
    claims: dict[str, object] = (
        dict(await client.fetch_user_info(access_token))
        if from_user_info
        else dict(id_token_claims)
    )
    identifier = claims.get(options.user_identifier_claim)
    if not isinstance(identifier, str) or identifier == "":
        raise AuthenticationError(
            f'The "{options.user_identifier_claim}" claim is missing or invalid '
            "in the OIDC response.",
        )
    if from_user_info:
        subject = claims.get("sub")
        expected = id_token_claims.get("sub")
        if (
            not isinstance(subject, str)
            or not isinstance(expected, str)
            or not hmac.compare_digest(expected, subject)
        ):
            raise AuthenticationError(
                'The "sub" claim from the UserInfo endpoint does not match the ID token.',
            )
    return claims


def build_passport(
    claims: Mapping[str, object],
    id_token_claims: Mapping[str, object],
    token_data: Mapping[str, object],
    user_provider: UserProviderInterface,
    options: OidcLoginOptions,
) -> SelfValidatingPassport:
    """Build the passport of a consumed callback around the claims the login read.

    The user is loaded by the firewall's user provider, from the configured
    identifier claim and with every claim passed as badge attributes: a
    provider implementing the attributes-based interface receives them, which
    is where mapping claims onto roles belongs.

    The ID token's own claims ride along as passport attributes: the token
    data for the token the login settles on, "auth_time" for the recency
    checks, "amr" and "acr" for the trust resolutions, and "sid" for the
    back-channel logout to match.

    Args:
        claims: The user claims the configured source read — the identifier
            claim and the badge attributes come from these.
        id_token_claims: The validated claims of the ID token — the
            ``auth_time``/``amr``/``acr``/``sid`` attributes come from
            these, whichever source the user claims were read from.
        token_data: The members of the token endpoint response.
        user_provider: Loads the user the identifier claim names.
        options: The flow's shape.
    """
    passport = SelfValidatingPassport(
        UserBadge(
            # fetch_user_claims has validated the identifier claim is a
            # non-empty string.
            cast("str", claims[options.user_identifier_claim]),
            user_loader=user_provider.load_user_by_identifier,
            attributes=claims,
        ),
    )
    passport.set_attribute(_TOKEN_DATA_ATTRIBUTE, dict(token_data))
    auth_time = id_token_claims.get("auth_time")
    passport.set_attribute(
        _AUTH_TIME_ATTRIBUTE,
        int(auth_time)
        if isinstance(auth_time, (int, float)) and not isinstance(auth_time, bool)
        else None,
    )
    # "amr" names the methods the provider actually used, from the registry of
    # RFC 8176, which is what lets a trust resolver require one of them and
    # not just any login.
    amr = id_token_claims.get("amr")
    passport.set_attribute(
        _AMR_ATTRIBUTE,
        (
            [method for method in cast("list[object]", amr) if isinstance(method, str)]
            if isinstance(amr, list)
            else []
        ),
    )
    # "acr" names the authentication context class the provider asserts, in
    # the vocabulary it shares with this application, and is the claim
    # answering the "acr_values" an authorization request asks for; it is
    # compared as-is, so anything but a non-empty string is no class.
    acr = id_token_claims.get("acr")
    passport.set_attribute(_ACR_ATTRIBUTE, acr if isinstance(acr, str) and acr else None)
    # "sid" names the provider session of this login (Back-Channel Logout 1.0,
    # Section 2.1), which is what a logout token names.
    sid = id_token_claims.get("sid")
    passport.set_attribute(_SID_ATTRIBUTE, sid if isinstance(sid, str) and sid else None)
    return passport
