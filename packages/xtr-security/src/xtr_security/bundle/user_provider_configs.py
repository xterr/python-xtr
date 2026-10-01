"""How a firewall finds its users, described as inert data.

Each configuration a ``type`` field tells apart names one way of loading a user:
an in-memory table, a chain of other providers, or a service the container
provides. The bundle's user-provider factories turn these into the provider
services a firewall authenticates against.
"""

from __future__ import annotations

import builtins  # noqa: TC003 -- field type read at runtime
from collections.abc import Mapping  # noqa: TC003 -- field type read at runtime
from dataclasses import dataclass, field
from typing import Literal

from xtr_security.exception import InvalidConfigurationError

__all__ = [
    "ChainUserProviderConfig",
    "InMemoryUserProviderConfig",
    "ServiceUserProviderConfig",
    "UserProviderConfig",
]


def _no_users() -> dict[str, Mapping[str, object]]:
    """The empty user table an in-memory provider config starts with."""
    return {}


@dataclass(frozen=True, slots=True)
class InMemoryUserProviderConfig:
    """Users declared inline, keyed by identifier.

    Each value is a mapping of the user's own fields — ``password``, ``roles``,
    ``enabled`` — the way an :class:`~xtr_security_core.InMemoryUser` is built.

    Attributes:
        users: The users, keyed by identifier.
        type: The discriminator, always ``"in_memory"``.
    """

    users: Mapping[str, Mapping[str, object]] = field(default_factory=_no_users)
    type: Literal["in_memory"] = "in_memory"


@dataclass(frozen=True, slots=True)
class ChainUserProviderConfig:
    """Several providers tried in turn, by the names they were registered under.

    Attributes:
        providers: The names of the providers to chain, in the order tried.
        type: The discriminator, always ``"chain"``.

    Raises:
        InvalidConfigurationError: When no provider is named.
    """

    providers: tuple[str, ...] = ()
    type: Literal["chain"] = "chain"

    def __post_init__(self) -> None:
        """Refuse an empty chain, which would load no user."""
        if not self.providers:
            raise InvalidConfigurationError(
                "A chain user provider needs at least one provider to chain.",
            )


@dataclass(frozen=True, slots=True)
class ServiceUserProviderConfig:
    """A user provider the container provides, named by its type and a qualifier.

    Attributes:
        service: The provider service's type, resolved from the container.
        qualifier: The qualifier that selects between registrations, or ``None``.
        type: The discriminator, always ``"service"``.

    Raises:
        InvalidConfigurationError: When ``service`` is not a class.
    """

    service: builtins.type
    qualifier: str | None = None
    type: Literal["service"] = "service"

    def __post_init__(self) -> None:
        """Check ``service`` is a class, since the container keys services by type."""
        if not isinstance(self.service, type):  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidConfigurationError(
                f"A service user provider needs a class, not {self.service!r}.",
            )


UserProviderConfig = (
    InMemoryUserProviderConfig | ChainUserProviderConfig | ServiceUserProviderConfig
)
"""Every kind of user-provider configuration, told apart by its ``type`` field."""
