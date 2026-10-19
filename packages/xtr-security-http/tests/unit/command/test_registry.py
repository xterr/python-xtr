"""The private command registry is a commands locator the command declares into."""

from __future__ import annotations

from xtr_console import CommandsLocator

from xtr_security_http.command._registry import SECURITY_HTTP_COMMANDS


def test_it_is_a_commands_locator() -> None:
    assert isinstance(SECURITY_HTTP_COMMANDS, CommandsLocator)
