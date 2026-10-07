"""The per-firewall contract the firewall runner and exception listener read.

The HTTP edge runs a firewall without knowing how its parts were built: the
runner authenticates through the manager and decides through the access
listener, and the exception listener answers a failure through the entry point
and handlers. Both read those parts off this contract, so the concrete context
that gathers them — built by the bundle — lives outside this package while the
runtime here depends only on the shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase

    from xtr_security_http.authentication.authenticator_manager_interface import (
        AuthenticatorManagerInterface,
    )
    from xtr_security_http.authorization.access_denied_handler_interface import (
        AccessDeniedHandlerInterface,
    )
    from xtr_security_http.entry_point.authentication_entry_point_interface import (
        AuthenticationEntryPointInterface,
    )
    from xtr_security_http.firewall.access_listener import AccessListener

__all__ = ["FirewallContextInterface"]


@runtime_checkable
class FirewallContextInterface(Protocol):
    """The runtime pieces of one firewall, resolved once and shared for its lifetime.

    Groups the manager that authenticates a request, the access listener that
    decides it, the entry point and handlers that answer it, and the OpenAPI
    scheme it contributes.

    Attributes:
        name: The firewall's name — the key it is looked up by, and the memo
            key that keeps its authentication to one pass per request.
        authenticator_manager: Runs the firewall's authenticators.
        access_listener: Decides a request against the firewall's rules.
        scheme: The FastAPI security object the firewall shows in OpenAPI.
        security: Whether the firewall authenticates at all; ``False`` lets
            every request through untouched.
        entry_point: Answers an unauthenticated request with a challenge.
        access_denied_handler: Answers a fully-authenticated caller's denial.
        scope_denied_handler: Answers a denied OAuth2 scope with its own
            challenge, ahead of the plain access-denied handler.
    """

    name: str
    authenticator_manager: AuthenticatorManagerInterface
    access_listener: AccessListener
    scheme: SecurityBase
    security: bool
    entry_point: AuthenticationEntryPointInterface | None
    access_denied_handler: AccessDeniedHandlerInterface | None
    scope_denied_handler: AccessDeniedHandlerInterface | None
