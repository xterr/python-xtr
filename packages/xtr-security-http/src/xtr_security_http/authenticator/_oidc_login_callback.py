"""Reading the OIDC authorization response a callback carries, and checking it."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_security_core.exception import AuthenticationError

from xtr_security_http._request_parameters import payload_parameter, query_parameter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["OidcCallback", "check_issuer", "check_provider_error", "read_callback"]


@final
@dataclass(frozen=True, slots=True)
class OidcCallback:
    """The parameters an authorization response carries.

    "form_post" has the provider post the response to the check path, the
    default "query" mode puts it in the redirect; both read the same names.
    """

    state: str
    code: str
    iss: str
    error: str
    error_description: str


def read_callback(request: ServerRequestInterface) -> OidcCallback:
    """Read the authorization response out of the callback request.

    A provider on another site makes a "form_post" response a cross-site
    POST, which carries no "SameSite=Lax" cookie, hence no session — so the
    parameters are read from the body only when the request is a POST, and
    from the query string otherwise.
    """
    reader = payload_parameter if request.get_method() == "POST" else query_parameter
    return OidcCallback(
        state=_text(reader(request, "state")),
        code=_text(reader(request, "code")),
        iss=_text(reader(request, "iss")),
        error=_text(reader(request, "error")),
        error_description=_text(reader(request, "error_description")),
    )


def check_issuer(iss: str, configuration: Mapping[str, object]) -> None:
    """Check the "iss" authorization response parameter of RFC 9207.

    It ties the callback to the provider that issued it: without it, a client
    registered with several providers can be led to send the code of an honest
    one to the token endpoint of a malicious one (the mix-up attack of the
    OAuth 2.0 Security BCP). It is checked before the "error" parameter, which
    RFC 9207, Section 2 requires it to accompany too.

    Raises:
        AuthenticationError: When the provider announces support for the
            parameter and the callback carries none, or when the one carried
            does not name the expected issuer.
    """
    if iss == "":
        # A provider announcing support for the parameter sends it on every
        # authorization response, so a callback without it did not come from
        # it.
        if configuration.get("authorization_response_iss_parameter_supported") is True:
            raise AuthenticationError(
                'The OIDC provider announces support for the "iss" authorization '
                "response parameter, but the callback does not carry it.",
            )
        return
    expected = configuration.get("issuer")
    if not isinstance(expected, str) or not hmac.compare_digest(expected, iss):
        raise AuthenticationError(
            'The OIDC callback "iss" parameter does not match the expected issuer.',
        )


def check_provider_error(error: str, error_description: str) -> None:
    """Refuse the error an authorization response carries, naming its description.

    Only the matched attempt was consumed by the caller, so an error for one
    tab does not cancel the logins pending in the others.

    Raises:
        AuthenticationError: When the provider answered with an error.
    """
    if error != "":
        description = error_description if error_description != "" else error
        raise AuthenticationError(f'OIDC provider returned an error: "{description}"')


def _text(value: object) -> str:
    """Narrow a callback parameter to the text it reads as when it is none."""
    return value if isinstance(value, str) else ""
