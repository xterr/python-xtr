"""Registering the console commands, and handing each one what it needs of the config.

Two steps, in two hooks, because a command is registered by the console bundle
rather than by this one: ``load_extension`` scans ``command/`` so the marker
:func:`~xtr_console.as_command` left on each class is read, and the console's
autoconfigurator turns each class it finds into a service. Only once that has
happened is there a definition to hand the settings a command cannot be
autowired — the class a registration is, whether the device flow runs at all,
where the key pair belongs — so that is done in ``process``.

The key material travels as the deployment wrote it, placeholders and all: a
definition's arguments have their environment resolved when the service is
built, which for a command is the one run that asks for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_dependency_injection import bundle_active

from .oauth2_server_config import OAuth2ServerConfig

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["configure_commands", "register_commands"]

#: The package whose scan declares every command this one ships.
_COMMAND_PACKAGE: Final = "xtr_security_oauth2_server.command"


def register_commands(services: ServiceConfigurator) -> None:
    """Scan ``command/``, so the console bundle registers every command declared there."""
    services.load(_COMMAND_PACKAGE)


def configure_commands(builder: ContainerBuilder) -> None:
    """Hand each command the settings the container cannot autowire for it.

    Returns without doing anything for a deployment running no console: the
    commands were then never scanned, and there is no definition to write on.
    """
    if not bundle_active(builder, "console"):
        return
    from xtr_security_oauth2_server.command import (  # noqa: PLC0415 -- imported only where a console is
        ClearExpiredTokensCommand,
        CreateClientCommand,
        GenerateKeyPairCommand,
    )

    config = builder.get_extension_config(OAuth2ServerConfig)
    server = config.authorization_server
    # Never asked whether a key is empty: key material a deployment reads out
    # of its environment arrives here as a placeholder, and asking such a
    # value a question about itself is what it cannot answer. Unset is
    # ``None``, and the command reports the setting when it is.
    public_key = config.resource_server.public_key
    settings: Mapping[type, Mapping[str, object]] = {
        CreateClientCommand: {"client_class": config.client.classname},
        ClearExpiredTokensCommand: {
            "enable_device_code_grant": server.enable_device_code_grant,
        },
        GenerateKeyPairCommand: {
            "private_key": server.private_key if server.private_key is not None else "",
            "public_key": public_key if public_key is not None else "",
            "passphrase": server.private_key_passphrase,
            "algorithm": server.signature_algorithm,
        },
    }
    for command, arguments in settings.items():
        _ = builder.get_definition(command).set_arguments(arguments)
