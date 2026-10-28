"""The access-denied handler that answers a scope shortfall the RFC 6750 way."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)

from xtr_security_http._challenge import no_store_headers, quote_auth_param
from xtr_security_http.authenticator._access_token_challenge import resource_metadata_value

from .access_denied_handler_interface import AccessDeniedHandlerInterface
from .oauth2_scope_voter import OAuth2ScopeVoter

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AccessDeniedError

    from xtr_security_http.access_token.sender_constraint_interface import (
        SenderConstraintInterface,
    )

__all__ = ["InsufficientScopeAccessDeniedHandler"]

#: The description RFC 6750 Section 3.1 gives for the ``insufficient_scope``
#: error code.
_ERROR_DESCRIPTION: Final = (
    "The request requires higher privileges than provided by the access token."
)


@final
class InsufficientScopeAccessDeniedHandler(AccessDeniedHandlerInterface):
    """Answers a denied scope check with ``403`` and a bearer scope challenge.

    When a bearer token is valid but lacks a scope a resource requires, RFC
    6750 says the answer is ``403`` with a ``WWW-Authenticate`` header naming
    ``error="insufficient_scope"`` and the ``scope`` the resource needs — and
    nothing in the body: the header carries all there is to say, so no scope
    detail leaks anywhere else. A denial no OAuth2 scope took part in is not
    this handler's to answer: it goes to the handler the application
    configured inside this one, or to the regular handling when it
    configured none, so a firewall mixing scopes with roles keeps answering
    the latter the way the application asked for.

    Attributes:
        realm: The protection realm named in the challenge, when set.
    """

    __slots__ = ("_inner", "_realm", "_resource_metadata_uri", "_responses", "_sender_constraint")

    def __init__(
        self,
        responses: ResponseFactoryInterface,
        realm: str | None = None,
        inner: AccessDeniedHandlerInterface | None = None,
        resource_metadata_uri: str | None = None,
        sender_constraint: SenderConstraintInterface | None = None,
    ) -> None:
        """Record the response factory and every part the challenge is built from.

        Args:
            responses: Builds the challenge responses this handler answers
                with, so it names no response class.
            realm: The protection realm named in the challenge, or ``None``.
            inner: Answers the denials no OAuth2 scope took part in, or
                ``None`` to leave them to the regular handling.
            resource_metadata_uri: Where the protected-resource metadata is
                published (RFC 9728, Section 5.1) — a client denied for a
                missing scope is the one that most needs to find the
                authorization server again — or ``None`` to name none.
            sender_constraint: What the firewall binds its access tokens to,
                which names the scheme of this challenge as it names the one
                of a ``401``, or ``None`` for ``Bearer``.
        """
        self._responses = responses
        self._realm = realm
        self._inner = inner
        self._resource_metadata_uri = resource_metadata_uri
        self._sender_constraint = sender_constraint

    @override
    async def handle(
        self, request: ServerRequestInterface, error: AccessDeniedError
    ) -> ResponseInterface | None:
        """Answer a scope shortfall with ``403`` and its challenge; leave the rest to ``inner``.

        The scopes every denied attribute asked for are merged — a denial may
        name several scope requests — and a denial that asked for none is not
        a scope shortfall at all: it goes to ``inner``, which answering
        ``None`` hands back to the regular access-denied handling.
        """
        scopes: list[str] = []
        for attribute in error.attributes:
            if not isinstance(attribute, str):
                continue
            required = OAuth2ScopeVoter.get_required_scopes(attribute)
            if required is not None:
                scopes.extend(required)
        if not scopes:
            if self._inner is None:
                return None
            return await self._inner.handle(request, error)
        response = self._responses.create_response(403)
        for name, value in no_store_headers(
            **{"www-authenticate": self._authenticate_header(request, scopes)},
        ).items():
            response = response.with_header(name.lower(), value)
        return response

    def _authenticate_header(self, request: ServerRequestInterface, scopes: list[str]) -> str:
        """Build the ``WWW-Authenticate`` header the ``403`` carries.

        A denial is no failure of the proof of possession, so the constraint
        answers it with its scheme and with nothing else; the parameters it
        would add to a ``401`` belong to that challenge, not this one. Every
        value that is ``None`` or empty is left out, and the scopes are
        deduplicated on first sight, so the header names each thing once.
        """
        scheme = (
            self._sender_constraint.get_challenge(None)[0]
            if self._sender_constraint is not None
            else "Bearer"
        )
        data = {
            "realm": self._realm,
            "error": "insufficient_scope",
            "error_description": _ERROR_DESCRIPTION,
            "scope": " ".join(dict.fromkeys(scopes)),
            "resource_metadata": resource_metadata_value(request, self._resource_metadata_uri),
        }
        values = [f"{name}={quote_auth_param(value)}" for name, value in data.items() if value]
        return scheme + (" " + ",".join(values) if values else "")
