"""The private command registry is a commands locator the bundle declares into."""

from __future__ import annotations

from xtr_console import CommandsLocator

from xtr_security_jwt.command._registry import JWT_COMMANDS


def test_it_is_a_commands_locator() -> None:
    assert isinstance(JWT_COMMANDS, CommandsLocator)
