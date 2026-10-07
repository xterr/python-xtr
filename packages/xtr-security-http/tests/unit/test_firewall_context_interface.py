"""The firewall-context contract the runner and exception listener read."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi.security import HTTPBearer

from tests.support.contexts import FakeFirewallContext
from xtr_security_http.firewall_context_interface import FirewallContextInterface

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase


def _context() -> FakeFirewallContext:
    scheme: SecurityBase = HTTPBearer(auto_error=False)
    return FakeFirewallContext(
        name="api",
        authenticator_manager=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        access_listener=object(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        scheme=scheme,
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
