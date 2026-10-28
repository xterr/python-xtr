"""The firewall-context contract the firewall and the exception listener read."""

from __future__ import annotations

from tests.support.contexts import FakeFirewallContext
from xtr_security_http.firewall_context_interface import FirewallContextInterface


def _context() -> FakeFirewallContext:
    return FakeFirewallContext(
        name="api",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
    )


def test_an_implementation_has_the_interface_in_its_mro() -> None:
    assert FirewallContextInterface in FakeFirewallContext.__mro__


def test_it_exposes_the_pieces_a_firewall_runs_on() -> None:
    context = _context()

    assert context.name == "api"
    assert context.security is True
    assert context.entry_point is None
    assert context.access_denied_handler is None
    assert context.scope_denied_handler is None
