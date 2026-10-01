"""A concrete firewall context for tests, now the http edge holds only the contract.

The concrete :class:`~xtr_security.firewall_context.FirewallContext` lives in the
bundle package, which the http edge cannot import; a test that needs a running
firewall builds this stand-in, which implements
:class:`~xtr_security_http.firewall_context_interface.FirewallContextInterface`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_security_http.firewall_context_interface import FirewallContextInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase
    from xtr_event_dispatcher_contracts import EventDispatcherInterface

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

__all__ = ["FakeFirewallContext"]


@dataclass(frozen=True, slots=True)
class FakeFirewallContext(FirewallContextInterface):
    """A firewall context a test builds directly, standing in for the bundle's."""

    name: str
    authenticator_manager: AuthenticatorManagerInterface
    access_listener: AccessListener
    dispatcher: EventDispatcherInterface
    scheme: SecurityBase
    security: bool = True
    entry_point: AuthenticationEntryPointInterface | None = None
    access_denied_handler: AccessDeniedHandlerInterface | None = None
    scope_denied_handler: AccessDeniedHandlerInterface | None = None
