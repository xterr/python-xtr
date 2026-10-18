"""The per-firewall contract the firewall and the exception listener read.

The HTTP edge runs a firewall without knowing how its parts were built: the
firewall's chain authenticates through the manager's listener step and
decides through the access step, and the exception listener answers a
failure through the entry point and handlers. Both read those parts off this
contract, so the concrete context that gathers them — built by the bundle —
lives outside this package while the runtime here depends only on the shape.

The firewall's listener chain is read through this contract too: the map's
``get_listeners`` answers a request with the matched firewall's chain, its
exception listener and its logout listener, so the firewall that runs the chain
never depends on how the bundle gathered it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
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
    from xtr_security_http.firewall.exception_listener import ExceptionListener
    from xtr_security_http.firewall.firewall_listener_interface import (
        FirewallListenerInterface,
    )

__all__ = ["FirewallContextInterface"]


@runtime_checkable
class FirewallContextInterface(Protocol):
    """The runtime pieces of one firewall, resolved once and shared for its lifetime.

    Groups the manager that authenticates a request, the access listener that
    decides it, the entry point and handlers that answer it, and the listener
    chain it runs — already ordered by the bundle's sorting pass, so the
    order it is held in is the order it runs in.

    Attributes:
        name: The firewall's name — the key it is looked up by, and the memo
            key that keeps its authentication to one pass per request.
        authenticator_manager: Runs the firewall's authenticators.
        access_listener: Decides a request against the firewall's rules.
        security: Whether the firewall authenticates at all; ``False`` lets
            every request through untouched.
        entry_point: Answers an unauthenticated request with a challenge.
        access_denied_handler: Answers a fully-authenticated caller's denial.
        scope_denied_handler: Answers a denied OAuth2 scope with its own
            challenge, ahead of the plain access-denied handler.
        listeners: The firewall's chain of listeners, in the order they run.
        exception_listener: The listener that answers a security error the
            firewall's request raised.
        logout_listener: The listener that performs a logout the firewall's
            request asks for, or ``None`` while the firewall has none.
    """

    name: str
    authenticator_manager: AuthenticatorManagerInterface
    access_listener: AccessListener
    security: bool
    entry_point: AuthenticationEntryPointInterface | None
    access_denied_handler: AccessDeniedHandlerInterface | None
    scope_denied_handler: AccessDeniedHandlerInterface | None
    listeners: tuple[FirewallListenerInterface, ...]
    exception_listener: ExceptionListener | None
    logout_listener: FirewallListenerInterface | None
