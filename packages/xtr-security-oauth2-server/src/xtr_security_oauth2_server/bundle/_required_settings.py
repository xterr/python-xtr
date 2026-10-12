"""Reporting a setting only the deployment can supply, where it is first needed.

The bundle builds and boots on its defaults: an application that has written no
configuration yet still gets a container, so its console runs and the key and
the clients it is missing can be minted. What it does not get is a working
server, and the place that says so is the service that cannot be built without
the setting — never the build, which would take the console down with it.

Each refusal names the setting, says what cannot be done without it, and points
at the file it belongs in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NoReturn

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = [
    "CONFIG_FILE",
    "refuse_without_persistence",
    "supplied",
    "supplied_scopes",
]

CONFIG_FILE: Final = "<app>/config/oauth2_server.py"
"""Where an application writes this bundle's configuration."""


def supplied(value: str | None, setting: str, because: str, hint: str = "") -> str:
    """Return ``value``, refusing when the deployment left ``setting`` unset.

    Args:
        value: What the deployment configured, if anything.
        setting: The setting it would have configured it under.
        because: What cannot be done without it, as a clause.
        hint: How a deployment comes by a value, when that is not obvious.

    Raises:
        InvalidConfigurationError: When nothing was configured.
    """
    if value:
        return value
    advice = f" {hint}" if hint else ""

    raise InvalidConfigurationError(
        f"The setting {setting} is not configured, so {because}. Write it in "
        f"{CONFIG_FILE}.{advice}",
    )


def supplied_scopes(available: Sequence[str]) -> tuple[str, ...]:
    """Return the scopes this deployment knows, refusing when it named none.

    Raises:
        InvalidConfigurationError: When no scope is available, which would
            leave every request asking for one refused and every token empty.
    """
    if available:
        return tuple(available)

    raise InvalidConfigurationError(
        "The setting scopes.available names no scope, so this server knows none and could "
        f"grant none. Name the scopes this deployment issues in {CONFIG_FILE}.",
    )


def refuse_without_persistence() -> NoReturn:
    """Refuse a server with nowhere for its clients and credentials to live.

    Raises:
        InvalidConfigurationError: Always. Registered in place of every store
            when ``persistence`` is unset, so the refusal arrives when one is
            first asked for rather than when the container is built.
    """
    raise InvalidConfigurationError(
        "The setting persistence is not configured, so there is nowhere for this server's "
        f"clients and credentials to live. Write it in {CONFIG_FILE}: "
        "persistence=InMemoryPersistenceConfig() for a test or a demonstration, "
        "OrmPersistenceConfig() for a database, CustomPersistenceConfig(...) for a store the "
        "application already has.",
    )
