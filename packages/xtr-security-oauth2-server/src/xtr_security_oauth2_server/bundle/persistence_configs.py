"""The three places a deployment's clients and credentials can live.

One of these, and exactly one, is named as the bundle's ``persistence``. They
share a file because they are the variants of one choice — the configuration a
``persistence`` field picks between — rather than three unrelated settings.
"""

from __future__ import annotations

from dataclasses import dataclass

# Every manager type here is a service the bundle aliases an interface to, so
# these annotations are read at runtime.
from xtr_security_oauth2_server.manager.access_token_manager_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    ClientManagerInterface,
)
from xtr_security_oauth2_server.manager.device_code_manager_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.service.credentials_revoker_interface import (  # noqa: TC001 -- a bundle config: its annotations are read at runtime
    CredentialsRevokerInterface,
)

__all__ = [
    "CustomPersistenceConfig",
    "InMemoryPersistenceConfig",
    "OrmPersistenceConfig",
]


@dataclass(frozen=True, slots=True)
class OrmPersistenceConfig:
    """Clients and credentials in a database, through the ORM integration.

    The package ships the mapping, not the revisions: the tables join the
    definitions of the named connection while the container is compiled, and
    the application writes its own revision with ``orm:migrations:diff``.

    Attributes:
        connection: The name of the connection the tables belong to and the
            managers read and write through.
        table_prefix: What every table of this package is named under, so its
            tables cannot collide with an application's own.
    """

    connection: str = "default"
    table_prefix: str = "oauth2_"


@dataclass(frozen=True, slots=True)
class InMemoryPersistenceConfig:
    """Clients and credentials in this process, forgotten when it ends.

    For tests, and for a demonstration a deployment runs once. Nothing is
    written down, so every client has to be registered again at each start —
    and the refresh-token manager's withdrawal is only atomic within one
    process, which is why a deployment serving more than one does not use this.
    """


@dataclass(frozen=True, slots=True)
class CustomPersistenceConfig:
    """Clients and credentials wherever the application already keeps them.

    The bundle registers no store of its own: it aliases each manager interface
    to the service named here, so an application that already has a client
    table, or keeps its credentials in something that is not a relational
    database, answers for all six and the rest of the package is unchanged.

    All six are required. Five of them are halves of one store, and the sixth
    is what withdraws everything issued to a client at once; a deployment
    answering for some of them and leaving the bundle to answer for the others
    would have two stores disagreeing about the same token.

    Attributes:
        access_token_manager: Where issued access tokens are kept.
        authorization_code_manager: Where issued authorization codes are kept.
        client_manager: Where registered clients are kept.
        refresh_token_manager: Where issued refresh tokens are kept.
        device_code_manager: Where issued device codes are kept.
        credentials_revoker: What withdraws everything issued to one client, or
            to one resource owner.
    """

    access_token_manager: type[AccessTokenManagerInterface]
    authorization_code_manager: type[AuthorizationCodeManagerInterface]
    client_manager: type[ClientManagerInterface]
    refresh_token_manager: type[RefreshTokenManagerInterface]
    device_code_manager: type[DeviceCodeManagerInterface]
    credentials_revoker: type[CredentialsRevokerInterface]
