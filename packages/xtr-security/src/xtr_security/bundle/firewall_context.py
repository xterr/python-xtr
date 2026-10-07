"""Everything one firewall needs to run, gathered in one place.

The bundle builds one of these per firewall and pairs each with its matcher in
the HTTP edge's :class:`~xtr_security_http.firewall_map.FirewallMap`. The HTTP
edge holds only the contract it reads —
:class:`~xtr_security_http.firewall_context_interface.FirewallContextInterface` —
so the concrete gathering of an authenticator manager, an access listener, an
entry point and the OpenAPI scheme lives here, next to the
:class:`~xtr_security.security.Security` facade and the firewall configuration.

This module is internal to the bundle: an application reads a firewall only
through :class:`~xtr_security_http.firewall_context_interface.FirewallContextInterface`,
never this class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_security_http.firewall_context_interface import FirewallContextInterface

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

__all__ = ["FirewallContext"]


@final
@dataclass(frozen=True, slots=True)
class FirewallContext(FirewallContextInterface):
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
    security: bool = True
    entry_point: AuthenticationEntryPointInterface | None = None
    access_denied_handler: AccessDeniedHandlerInterface | None = None
    scope_denied_handler: AccessDeniedHandlerInterface | None = None
