"""The concrete firewall context gathers one firewall's runtime pieces."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pytest
from fastapi.security import HTTPBearer
from xtr_security_http.firewall_context_interface import FirewallContextInterface

from xtr_security.bundle.firewall_context import FirewallContext

if TYPE_CHECKING:
    from fastapi.security.base import SecurityBase


def _context(**overrides: object) -> FirewallContext:
    scheme: SecurityBase = HTTPBearer(auto_error=False)
    fields: dict[str, object] = {
        "name": "api",
        "authenticator_manager": object(),
        "access_listener": object(),
        "scheme": scheme,
    }
    fields.update(overrides)
    return FirewallContext(**fields)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def test_it_implements_the_http_context_interface() -> None:
    assert FirewallContextInterface in FirewallContext.__mro__


def test_it_holds_the_pieces_it_is_given() -> None:
    manager = object()
    context = _context(authenticator_manager=manager, name="admin")

    assert context.name == "admin"
    assert context.authenticator_manager is manager


def test_it_defaults_security_on_and_the_handlers_off() -> None:
    context = _context()

    assert context.security is True
    assert context.entry_point is None
    assert context.access_denied_handler is None
    assert context.scope_denied_handler is None


def test_it_is_frozen() -> None:
    context = _context()

    with pytest.raises(dataclasses.FrozenInstanceError):
        context.security = False  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]
