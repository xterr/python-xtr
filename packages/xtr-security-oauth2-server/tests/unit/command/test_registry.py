"""The private command registry is a commands locator every command declares into."""

from __future__ import annotations

from xtr_console import CommandsLocator, default_registry

from xtr_security_oauth2_server import command
from xtr_security_oauth2_server.command._registry import OAUTH2_SERVER_COMMANDS

NAMES = frozenset(
    {
        "oauth2-server:create-client",
        "oauth2-server:update-client",
        "oauth2-server:delete-client",
        "oauth2-server:list-clients",
        "oauth2-server:clear-expired-tokens",
        "oauth2-server:generate-keypair",
    },
)
"""Every command this package ships, named as a shell names it."""


def test_it_is_a_commands_locator() -> None:
    assert isinstance(OAUTH2_SERVER_COMMANDS, CommandsLocator)


def test_every_command_declares_into_it() -> None:
    # Importing the package is what declares them, which is what the bundle's
    # scan of it does.
    assert len(command.__all__) == len(NAMES)
    declared = {descriptor.name for descriptor in OAUTH2_SERVER_COMMANDS.commands()}

    assert declared == set(NAMES)


def test_none_of_them_leaks_into_the_process_wide_registry() -> None:
    # A container-less application reads the default registry, and these
    # commands cannot be built without one.
    process_wide = {descriptor.name for descriptor in default_registry().commands()}

    assert process_wide & NAMES == set()
