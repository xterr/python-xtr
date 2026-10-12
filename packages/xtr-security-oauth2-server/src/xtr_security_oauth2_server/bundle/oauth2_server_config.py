"""The configuration the OAuth 2.0 server bundle builds a deployment from."""

from __future__ import annotations

from dataclasses import dataclass, field

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

from .authorization_server_config import AuthorizationServerConfig
from .client_config import ClientConfig

# One of the three persistence variants is named here, and the bundle reads
# which one it is to decide what to register, so these are read at runtime.
from .persistence_configs import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    CustomPersistenceConfig,
    InMemoryPersistenceConfig,
    OrmPersistenceConfig,
)
from .resource_server_config import ResourceServerConfig
from .scopes_config import ScopesConfig

__all__ = ["OAuth2ServerConfig"]

#: What a scope becomes a role under, so an access token's permissions reach
#: the same authorization checks every other role does.
DEFAULT_ROLE_PREFIX = "ROLE_OAUTH2_"


@dataclass(frozen=True, slots=True)
class OAuth2ServerConfig:
    """Everything this deployment's authorization server is.

    Buildable with no arguments, because the bundle must be declarable before
    an application has written a line of configuration — and the console must
    keep running on a fresh application, so that the key and the clients it is
    missing can be minted. It is not *usable* that way: each setting still
    missing is reported where it is first needed, by the service that cannot be
    built without it, as an
    :class:`~xtr_security_oauth2_server.exception.InvalidConfigurationError`
    naming the setting and the file to write it in — never by the build, which
    would take the console down with it.

    ``persistence`` is the one choice with no default at all. The three
    variants are a real decision — a database, this process's memory, or the
    application's own store — and each registers different services, so
    guessing one would silently give a deployment a server that forgets every
    token it issued when the process ends.

    Attributes:
        authorization_server: What signs, seals, issues and runs.
        resource_server: What an API reads this server's tokens against.
        scopes: The scopes this deployment knows, and its defaults.
        persistence: Where clients and credentials live. Required.
        client: Which class registered clients are.
        role_prefix: What a scope becomes a role under, so that a token
            carrying ``orders:read`` grants ``ROLE_OAUTH2_ORDERS:READ``.
    """

    authorization_server: AuthorizationServerConfig = field(
        default_factory=AuthorizationServerConfig,
    )
    resource_server: ResourceServerConfig = field(default_factory=ResourceServerConfig)
    scopes: ScopesConfig = field(default_factory=ScopesConfig)
    persistence: (
        OrmPersistenceConfig | InMemoryPersistenceConfig | CustomPersistenceConfig | None
    ) = None
    client: ClientConfig = field(default_factory=ClientConfig)
    role_prefix: str = DEFAULT_ROLE_PREFIX

    def __post_init__(self) -> None:
        """Refuse an empty role prefix.

        Raises:
            InvalidConfigurationError: When the role prefix is empty, which
                would turn a scope straight into a role and let a token grant
                ``ROLE_ADMIN`` by asking for the scope ``admin``.
        """
        if not self.role_prefix:
            raise InvalidConfigurationError(
                "The setting role_prefix is empty; without a prefix a scope becomes a role of "
                "its own name, so a client asking for the scope 'admin' would be granted "
                "ROLE_ADMIN. Name a prefix, such as 'ROLE_OAUTH2_'.",
            )
