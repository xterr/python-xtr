"""The access-denied handler that answers a scope shortfall the RFC 6750 way."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)

from xtr_security_http._challenge import json_challenge, quote_auth_param

from .access_denied_handler_interface import AccessDeniedHandlerInterface
from .oauth2_scope_voter import parse_oauth2_scope

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.exception import AccessDeniedError

__all__ = ["InsufficientScopeAccessDeniedHandler"]


@final
class InsufficientScopeAccessDeniedHandler(AccessDeniedHandlerInterface):
    """Answers a denied scope check with ``403`` and a bearer scope challenge.

    When a bearer token is valid but lacks a scope a resource requires, RFC
    6750 says the answer is ``403`` with a ``WWW-Authenticate: Bearer`` header
    naming ``error="insufficient_scope"`` and the ``scope`` the resource needs.
    This handler reads the scopes out of the denied ``OAUTH2_SCOPE(...)``
    attribute and writes that challenge, with the realm when one is configured.

    Attributes:
        realm: The protection realm named in the challenge, when set.
    """

    __slots__ = ("_realm", "_responses")

    def __init__(self, responses: ResponseFactoryInterface, realm: str | None = None) -> None:
        """Record the response factory and the realm named in the challenge, if any.

        Args:
            responses: Builds the challenge responses this handler answers
                with, so it names no response class.
            realm: The protection realm named in the challenge, or ``None``.
        """
        self._responses = responses
        self._realm = realm

    @override
    async def handle(
        self, request: ServerRequestInterface, error: AccessDeniedError
    ) -> ResponseInterface | None:
        """Return a ``403`` carrying the RFC 6750 insufficient-scope challenge."""
        del request
        scope = self._required_scope(error)
        parts = ["Bearer"]
        if self._realm is not None:
            parts.append(f"realm={quote_auth_param(self._realm)}")
        parts.append('error="insufficient_scope"')
        parts.append(
            "error_description="
            + quote_auth_param("The request requires higher privileges than provided."),
        )
        if scope:
            parts.append(f"scope={quote_auth_param(scope)}")
        challenge = parts[0] + " " + ", ".join(parts[1:])
        return await json_challenge(
            self._responses,
            403,
            {"error": "insufficient_scope"},
            {"WWW-Authenticate": challenge},
        )

    def _required_scope(self, error: AccessDeniedError) -> str:
        """Read the space-joined scopes out of the denied scope attribute."""
        for attribute in error.attributes:
            scopes = parse_oauth2_scope(attribute)
            if scopes is not None:
                return " ".join(scopes)
        return ""
