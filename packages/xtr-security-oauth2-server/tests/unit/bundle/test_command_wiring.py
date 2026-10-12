"""The commands are registered where a console is, and handed what they need.

A command is registered by the console bundle rather than by this one, so this
bundle has two jobs: scan ``command/`` so there is anything to register, and
hand each command the settings the container cannot autowire. Both are asserted
by building the thing: a command handed the wrong settings, or none, cannot be
resolved at all.
"""

from __future__ import annotations

import pytest

from tests.support.building import processing_builder
from tests.support.console import IN_MEMORY_APP, console_kernel, running
from tests.support.served import oauth2_kernel
from tests.support.signing import ALGORITHM
from xtr_security_oauth2_server.bundle._command_wiring import configure_commands
from xtr_security_oauth2_server.command import (
    ClearExpiredTokensCommand,
    CreateClientCommand,
    DeleteClientCommand,
    GenerateKeyPairCommand,
    ListClientsCommand,
    UpdateClientCommand,
)
from xtr_security_oauth2_server.model.client import Client

pytestmark = pytest.mark.anyio

COMMANDS = (
    ClearExpiredTokensCommand,
    CreateClientCommand,
    DeleteClientCommand,
    GenerateKeyPairCommand,
    ListClientsCommand,
    UpdateClientCommand,
)
"""Every command this package ships, as the class the container builds."""

NAMES = (
    "oauth2-server:create-client",
    "oauth2-server:update-client",
    "oauth2-server:delete-client",
    "oauth2-server:list-clients",
    "oauth2-server:clear-expired-tokens",
    "oauth2-server:generate-keypair",
)
"""The same six, as a shell names them."""


def _command_id(command: type) -> str:
    """Name a parametrised case after the command it is about."""
    return command.__name__


@pytest.mark.parametrize("command", COMMANDS, ids=_command_id)
async def test_every_command_resolves_from_the_container(command: type) -> None:
    async with running(console_kernel()) as (_application, container):
        assert await container.get(command) is not None


@pytest.mark.parametrize("command", COMMANDS, ids=_command_id)
async def test_an_application_listing_this_bundle_alone_still_gets_the_commands(
    command: type,
) -> None:
    # The console is a peer this bundle brings along, so an application that
    # installed xtr-console has the commands without listing anything.
    async with await oauth2_kernel(IN_MEMORY_APP).boot() as booted:
        assert booted.container.has(command)


async def test_the_application_answers_to_every_command_of_this_package() -> None:
    async with running(console_kernel()) as (application, _container):
        declared = {
            descriptor.name: descriptor.target for descriptor in application.commands.commands()
        }

    for name in NAMES:
        assert name in declared
    for command in COMMANDS:
        assert command in declared.values()


async def test_the_configured_client_class_reaches_the_command_that_registers_one() -> None:
    async with running(console_kernel()) as (_application, container):
        command = await container.get(CreateClientCommand)

        assert command._client_class is Client


async def test_the_configured_algorithm_reaches_the_command_that_mints_a_key() -> None:
    async with running(console_kernel()) as (_application, container):
        command = await container.get(GenerateKeyPairCommand)

        # What a run naming no algorithm mints for: the one this deployment signs with.
        assert command._algorithm == ALGORITHM


async def test_whether_the_device_flow_runs_reaches_the_command_that_sweeps() -> None:
    async with running(console_kernel()) as (_application, container):
        command = await container.get(ClearExpiredTokensCommand)

        assert command._enable_device_code_grant is True


def test_a_build_with_no_console_is_left_without_command_definitions() -> None:
    # A build without the console cannot be had through a kernel here: the
    # console bundle is a peer this one requires, and a required bundle
    # inherits the requirer's activity, so installing xtr-console is enough to
    # activate it. What is asserted is the guard itself — handed a build whose
    # active bundles do not include the console, it writes nothing, because
    # nothing scanned ``command/`` and there is no definition to write on.
    builder = processing_builder({"kernel.bundles": {"oauth2_server": "oauth2_server:Bundle"}})

    configure_commands(builder)

    for command in COMMANDS:
        assert not builder.has_definition(command)
