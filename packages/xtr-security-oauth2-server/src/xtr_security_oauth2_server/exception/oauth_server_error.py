"""The protocol's own error answer: a named error, its status, and the payload sent with it."""

from __future__ import annotations

import json
from html import escape
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self
from urllib.parse import urlencode

from .oauth2_error import OAuth2Error

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["OAuthServerError"]

#: The one error whose answer names the authentication scheme back at the
#: client, so the rule in :meth:`OAuthServerError.get_http_headers` and the
#: constructor that sets it cannot drift apart.
_INVALID_CLIENT: Final[str] = "invalid_client"


class OAuthServerError(OAuth2Error):
    """A refusal the protocol has a name for, carrying everything needed to answer it.

    Raised wherever a request cannot be honoured: an unknown grant type, a
    client that failed authentication, a code that was already redeemed. The
    error is not only a message — it is the answer, so whoever catches it asks
    for one with :meth:`generate_http_response` and sends it.

    Raise it through one of the named constructors, never by naming a number:
    each one fixes the error name the protocol uses, the status the answer
    carries and the number the error is catalogued under, and that triple is
    the contract a client reads. Chain the cause the usual way —
    ``raise OAuthServerError.invalid_refresh_token(hint) from cause`` — so the
    traceback keeps what actually went wrong without the answer naming it.

    An error carrying a redirect URI is answered as a redirect rather than as
    a document: an authorization request that named a redirect gets its refusal
    delivered there, because that is where the client is waiting.
    """

    def __init__(  # noqa: PLR0913, PLR0917 -- these six together are one error answer
        self,
        message: str,
        code: int,
        error_type: str,
        http_status_code: int = 400,
        hint: str | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        """Record one answer: what went wrong, what to call it, and how to send it.

        ``message`` and ``error_type`` become the ``error_description`` and the
        ``error`` of the payload, and ``code`` is the number the error is
        catalogued under — stable across versions, so a caller may switch on
        it. A ``hint`` is sent when there is one, and an empty string counts as
        one: only ``None`` leaves the field out. A ``redirect_uri`` is where
        the refusal is to be delivered, when the request named anywhere.
        """
        super().__init__(message)
        self._code: int = code
        self._error_type: str = error_type
        self._http_status_code: int = http_status_code
        self._hint: str | None = hint
        self._redirect_uri: str | None = redirect_uri
        self._server_request: ServerRequestInterface | None = None
        payload: dict[str, str] = {"error": error_type, "error_description": message}
        if hint is not None:
            payload["hint"] = hint
        self._payload: dict[str, str] = payload

    @classmethod
    def unsupported_grant_type(cls) -> Self:
        """The request named a grant this server does not run."""
        message = "The authorization grant type is not supported by the authorization server."
        hint = "Check that all required parameters have been provided"

        return cls(message, 2, "unsupported_grant_type", hint=hint)

    @classmethod
    def invalid_request(cls, parameter: str, hint: str | None = None) -> Self:
        """A parameter is missing, repeated or unusable.

        Names ``parameter`` in the hint unless the caller has something more
        useful to say about it.
        """
        message = (
            "The request is missing a required parameter, includes an invalid parameter value, "
            "includes a parameter more than once, or is otherwise malformed."
        )
        told = hint if hint is not None else f"Check the `{parameter}` parameter"

        return cls(message, 3, "invalid_request", hint=told)

    @classmethod
    def invalid_client(cls, server_request: ServerRequestInterface) -> Self:
        """The client could not be authenticated.

        Takes the request because the answer depends on how the client tried:
        one that sent an ``Authorization`` header is told which scheme to try
        again with. The message says no more than that authentication failed —
        which client, and why, is never told to the caller.
        """
        error = cls("Client authentication failed", 4, _INVALID_CLIENT, 401)
        error.set_server_request(server_request)

        return error

    @classmethod
    def invalid_scope(cls, scope: str, redirect_uri: str | None = None) -> Self:
        """The request asked for a scope this server does not know.

        The scope is repeated back in the hint, escaped: it came from the
        request, and an application may well render the hint in a page.
        """
        if scope == "":
            hint = "Specify a scope in the request or set a default scope"
        else:
            hint = f"Check the `{escape(scope)}` scope"
        message = "The requested scope is invalid, unknown, or malformed"

        return cls(message, 5, "invalid_scope", hint=hint, redirect_uri=redirect_uri)

    @classmethod
    def invalid_credentials(cls) -> Self:
        """The user's own credentials were wrong."""
        return cls("The user credentials were incorrect.", 6, "invalid_grant")

    @classmethod
    def server_error(cls, hint: str) -> Self:
        """Something broke that the request could have done nothing about.

        The reason goes into the description rather than the hint, because
        there is nothing the client can change about it.
        """
        message = (
            "The authorization server encountered an unexpected condition which prevented it "
            f"from fulfilling the request: {hint}"
        )

        return cls(message, 7, "server_error", 500)

    @classmethod
    def invalid_refresh_token(cls, hint: str | None = None) -> Self:
        """The refresh token could not be read, or is no longer usable."""
        return cls("The refresh token is invalid.", 8, "invalid_grant", hint=hint)

    @classmethod
    def access_denied(cls, hint: str | None = None, redirect_uri: str | None = None) -> Self:
        """The user, or the server itself, refused the request."""
        message = "The resource owner or authorization server denied the request."

        return cls(message, 9, "access_denied", 401, hint, redirect_uri)

    @classmethod
    def invalid_grant(cls, hint: str = "") -> Self:
        """The grant presented is not one this client can redeem now.

        The catch-all for a code or refresh token that is unknown, expired,
        revoked, bound to another redirect URI or issued to another client —
        deliberately one answer for all of them, so a client cannot tell which.
        """
        message = (
            "The provided authorization grant (e.g., authorization code, resource owner "
            "credentials) or refresh token is invalid, expired, revoked, does not match the "
            "redirection URI used in the authorization request, or was issued to another client."
        )

        return cls(message, 10, "invalid_grant", hint=hint)

    @classmethod
    def expired_token(cls, hint: str | None = None) -> Self:
        """The device code polled for has expired and its session is over."""
        message = (
            "The `device_code` has expired and the device authorization session has concluded."
        )

        return cls(message, 11, "expired_token", hint=hint)

    @classmethod
    def authorization_pending(cls, hint: str = "") -> Self:
        """The user has not finished approving the device yet; keep polling."""
        message = (
            "The authorization request is still pending as the end user hasn't yet completed "
            "the user interaction steps. The client SHOULD repeat the Access Token Request to "
            "the token endpoint"
        )

        return cls(message, 12, "authorization_pending", hint=hint)

    @classmethod
    def slow_down(cls, hint: str = "") -> Self:
        """The device polled too soon; it must wait five seconds longer from now on."""
        message = (
            "The authorization request is still pending and polling should continue, but the "
            "interval MUST be increased by 5 seconds for this and all subsequent requests."
        )

        return cls(message, 13, "slow_down", hint=hint)

    @classmethod
    def unauthorized_client(cls, hint: str | None = None) -> Self:
        """The client authenticated, but is not allowed this grant."""
        message = "The authenticated client is not authorized to use this authorization grant type."

        return cls(message, 14, "unauthorized_client", hint=hint)

    @classmethod
    def unsupported_token_type(cls, hint: str | None = None) -> Self:
        """The client named a kind of token this server cannot act on.

        This server issues two kinds of token — access tokens and refresh
        tokens — and withdraws either. A token read as a third kind, which
        only a deployment that reads tokens of its own can produce, is refused
        rather than answered as though it had been withdrawn (RFC 7009,
        Section 2.2.1).
        """
        message = (
            "The authorization server does not support the revocation of the presented token type."
        )

        return cls(message, 15, "unsupported_token_type", hint=hint)

    def get_code(self) -> int:
        """Return the number this error is catalogued under."""
        return self._code

    def get_error_type(self) -> str:
        """Return the error name the answer carries as ``error``."""
        return self._error_type

    def get_http_status_code(self) -> int:
        """Return the status a document answer carries.

        It is never 302, even for an error that redirects: the status of the
        refusal and the fact that it is delivered by redirect are two different
        things, so an application overriding error pages can let the redirects
        through — see :meth:`has_redirect`.
        """
        return self._http_status_code

    def get_hint(self) -> str | None:
        """Return what the client could change, or ``None`` when there is nothing."""
        return self._hint

    def has_redirect(self) -> bool:
        """Tell whether this refusal is to be delivered to a redirect URI."""
        return self._redirect_uri is not None

    def get_redirect_uri(self) -> str | None:
        """Return where the refusal is to be delivered, if anywhere."""
        return self._redirect_uri

    def get_payload(self) -> Mapping[str, str]:
        """Return what the answer says, as a read-only view.

        ``error`` and ``error_description`` always, ``hint`` when there is one.
        Use :meth:`set_payload` to change it; the view answers the payload as
        it stood when it was asked for.
        """
        return MappingProxyType(self._payload)

    def set_payload(self, payload: Mapping[str, str]) -> None:
        """Replace what the answer says.

        For a caller that has to shape the answer itself — adding a field an
        extension defines, or dropping the hint from a public error.
        """
        self._payload = dict(payload)

    def set_server_request(self, server_request: ServerRequestInterface) -> None:
        """Record the request this refusal answers.

        Only the client-authentication answer reads it, to name back the
        scheme the client tried.
        """
        self._server_request = server_request

    def get_http_headers(self) -> Mapping[str, str]:
        """Return the headers a document answer carries, their names lowercased.

        A client that tried to authenticate with an ``Authorization`` header
        and failed is told which scheme to try again with: RFC 6749 §5.2 has
        the 401 answering such a request carry ``WWW-Authenticate`` for the
        scheme the client used. A client that put its credentials in the form
        instead attempted no scheme, so none is named — and a header handed on
        empty, as some servers do when the client sent none, counts as no
        attempt either.
        """
        headers = {"content-type": "application/json"}
        request = self._server_request
        attempted = "" if request is None else request.get_header_line("Authorization")
        if self._error_type == _INVALID_CLIENT and attempted != "":
            scheme = "Bearer" if attempted.startswith("Bearer") else "Basic"
            headers["www-authenticate"] = f'{scheme} realm="OAuth"'

        return headers

    def generate_http_response(
        self,
        response: ResponseInterface,
        use_fragment: bool = False,
    ) -> ResponseInterface:
        """Build the answer to this error on top of ``response``.

        With a redirect URI, the answer is a 302 whose ``Location`` carries the
        payload — in the query, or in the fragment when ``use_fragment`` is
        set, as a refusal to an implicit-grant request needs. Nothing else is
        added to it: a browser is going to follow the redirect, and a content
        type would only describe a body that is not there.

        Without a redirect URI, the answer is the payload as a JSON document,
        carrying this error's status and headers.

        Asking twice answers the same thing: the error is left as it was, so
        the redirect target does not grow a separator each time.
        """
        payload = dict(self._payload)
        if self._redirect_uri is not None:
            marker = "#" if use_fragment else "?"
            separator = marker if marker not in self._redirect_uri else "&"
            target = f"{self._redirect_uri}{separator}{urlencode(payload)}"

            return response.with_status(302).with_header("Location", target)

        answer = response
        for name, value in self.get_http_headers().items():
            answer = answer.with_header(name, value)
        answer = answer.with_status(self._http_status_code)
        _ = answer.get_body().write(json.dumps(payload).encode())

        return answer
