"""Registering where a deployment's clients and credentials live.

One of four answers: in this process, in a database, in stores the application
answers for, or — until a deployment says — in something that refuses and names
the setting. Kept apart from the bundle because it is the one choice that
decides a whole set of services, and because two of the four have something to
say once every bundle has loaded.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_dependency_injection import bundle_active

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)
from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)
from xtr_security_oauth2_server.manager.authorization_code_manager_interface import (
    AuthorizationCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.device_code_manager_interface import (
    DeviceCodeManagerInterface,
)
from xtr_security_oauth2_server.manager.in_memory.access_token_manager import (
    AccessTokenManager as InMemoryAccessTokenManager,
)
from xtr_security_oauth2_server.manager.in_memory.authorization_code_manager import (
    AuthorizationCodeManager as InMemoryAuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.in_memory.client_manager import (
    ClientManager as InMemoryClientManager,
)
from xtr_security_oauth2_server.manager.in_memory.device_code_manager import (
    DeviceCodeManager as InMemoryDeviceCodeManager,
)
from xtr_security_oauth2_server.manager.in_memory.refresh_token_manager import (
    RefreshTokenManager as InMemoryRefreshTokenManager,
)
from xtr_security_oauth2_server.manager.orm.access_token_manager import (
    AccessTokenManager as OrmAccessTokenManager,
)
from xtr_security_oauth2_server.manager.orm.authorization_code_manager import (
    AuthorizationCodeManager as OrmAuthorizationCodeManager,
)
from xtr_security_oauth2_server.manager.orm.client_manager import (
    ClientManager as OrmClientManager,
)
from xtr_security_oauth2_server.manager.orm.device_code_manager import (
    DeviceCodeManager as OrmDeviceCodeManager,
)
from xtr_security_oauth2_server.manager.orm.refresh_token_manager import (
    RefreshTokenManager as OrmRefreshTokenManager,
)
from xtr_security_oauth2_server.manager.refresh_token_manager_interface import (
    RefreshTokenManagerInterface,
)
from xtr_security_oauth2_server.persistence.mapping.driver import Driver
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

from ._application_stores import named_stores, register_custom
from ._no_persistence import unconfigured_store_factories
from ._parameters import PERSISTENCE_ORM_CONNECTION, PERSISTENCE_ORM_ENABLED
from ._persistence_factories import (
    access_token_manager_factory,
    authorization_code_manager_factory,
    client_manager_factory,
    credentials_revoker_factory,
    device_code_manager_factory,
    refresh_token_manager_factory,
)
from .persistence_configs import (
    CustomPersistenceConfig,
    InMemoryPersistenceConfig,
    OrmPersistenceConfig,
)

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator
    from xtr_orm.bundle import OrmMappingsPass

    from .oauth2_server_config import OAuth2ServerConfig

__all__ = ["PersistenceWiring"]

#: What a deployment keeping its credentials in a database but listing no ORM
#: bundle is told, since nothing would open the connection they live on.
_NO_ORM_BUNDLE = (
    "This deployment keeps its OAuth 2.0 clients and credentials in a database, but the orm "
    "bundle is not active, so there is no connection to read them through. List OrmBundle in "
    "the application's bundles, or choose another persistence."
)


@final
class PersistenceWiring:
    """Registers the stores of one deployment, and refuses one nothing can serve.

    It outlives the ``load_extension`` hook because two of its answers are only
    final later: the mappings pass is handed its driver while the services are
    registered, and a store an application named is looked for once every
    bundle has loaded and every scan has been read.
    """

    __slots__ = ("_custom", "_mappings")

    def __init__(self) -> None:
        """Hold nothing yet: the pass arrives in ``build``, the stores in ``load``."""
        self._mappings: OrmMappingsPass | None = None
        self._custom: CustomPersistenceConfig | None = None

    def mappings_pass(self) -> OrmMappingsPass | None:
        """Return the pass loading this package's tables, when the ORM is installed.

        Guarded by the import rather than by configuration, because the pass
        has to be registered while the container is being wired — before the
        persistence a deployment chose has been read. It is remembered, so the
        driver can be handed over once there is one.
        """
        try:
            from xtr_orm.bundle import (  # noqa: PLC0415 -- an optional extra, probed where it is needed
                OrmMappingsPass,
            )
        except ImportError:
            return None
        self._mappings = OrmMappingsPass(PERSISTENCE_ORM_CONNECTION, PERSISTENCE_ORM_ENABLED)

        return self._mappings

    def register(
        self,
        config: OAuth2ServerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register where this deployment's clients and credentials live."""
        persistence = config.persistence
        if isinstance(persistence, InMemoryPersistenceConfig):
            _register_in_memory(config, services)
        elif isinstance(persistence, OrmPersistenceConfig):
            self._register_orm(config, persistence, services, builder)
        elif isinstance(persistence, CustomPersistenceConfig):
            self._custom = persistence
            register_custom(persistence, services)
        else:
            # Nothing was chosen. Every store refuses when it is first asked
            # for, naming the setting — rather than the container reporting an
            # unknown service, which says nothing about what is missing.
            for factory in unconfigured_store_factories():
                _ = services.set(factory)

    def refuse_what_nothing_can_serve(self, builder: ContainerBuilder) -> None:
        """Refuse a persistence this container cannot answer for.

        Raises:
            InvalidConfigurationError: When this deployment keeps its clients
                and credentials in a database and the ORM bundle is not active,
                or when it named its own stores and one of them is not a
                registered service.
        """
        self._refuse_unregistered_stores(builder)
        if not builder.has_parameter(PERSISTENCE_ORM_ENABLED):
            return
        if not bundle_active(builder, "orm"):
            raise InvalidConfigurationError(_NO_ORM_BUNDLE)

    def _register_orm(
        self,
        config: OAuth2ServerConfig,
        persistence: OrmPersistenceConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Keep everything in the named connection's tables."""
        from xtr_security_oauth2_server.service.credentials_revoker.orm_credentials_revoker import (  # noqa: PLC0415 -- imported where the ORM persistence is wired
            OrmCredentialsRevoker,
        )

        server = config.authorization_server
        connection = persistence.connection
        # The flag the mappings pass and the bundle's own `process` read: it
        # being set at all is what says the tables are wanted.
        wanted = True
        builder.set_parameter(PERSISTENCE_ORM_ENABLED, wanted)
        builder.set_parameter(PERSISTENCE_ORM_CONNECTION, connection)
        client_class = config.client.classname
        _ = services.set(client_manager_factory(connection, client_class))
        services.alias(ClientManagerInterface, OrmClientManager)
        _ = services.set(access_token_manager_factory(connection, server.persist_access_token))
        services.alias(AccessTokenManagerInterface, OrmAccessTokenManager)
        _ = services.set(refresh_token_manager_factory(connection))
        services.alias(RefreshTokenManagerInterface, OrmRefreshTokenManager)
        _ = services.set(authorization_code_manager_factory(connection))
        services.alias(AuthorizationCodeManagerInterface, OrmAuthorizationCodeManager)
        _ = services.set(device_code_manager_factory(connection))
        services.alias(DeviceCodeManagerInterface, OrmDeviceCodeManager)
        _ = services.set(
            credentials_revoker_factory(
                connection,
                server.persist_access_token,
                server.enable_device_code_grant,
            ),
        )
        services.alias(CredentialsRevokerInterface, OrmCredentialsRevoker)
        if self._mappings is not None:
            # The tables join the connection's definitions while the container
            # is compiled, which is early enough for a revision to be diffed
            # from them.
            self._mappings.set_driver(
                Driver(
                    client_class,
                    server.persist_access_token,
                    persistence.table_prefix,
                    server.enable_device_code_grant,
                ),
            )

    def _refuse_unregistered_stores(self, builder: ContainerBuilder) -> None:
        """Refuse a named store nothing registered, naming every one that is missing.

        Run once every bundle has loaded and every scan has been read, which
        is the earliest moment the answer is final: a store may be registered
        by the application's own scan or by a bundle loaded after this one.

        Raises:
            InvalidConfigurationError: When any store named under
                ``persistence.custom`` is not a service of this container.
        """
        custom = self._custom
        if custom is None:
            return
        missing = [
            f"{setting} = {store.__qualname__}"
            for setting, _interface, store in named_stores(custom)
            if not (builder.has_definition(store) or builder.has_alias(store))
        ]
        if not missing:
            return
        named = "\n".join(f"  - {entry}" for entry in missing)
        raise InvalidConfigurationError(
            "This deployment keeps its OAuth 2.0 clients and credentials in stores of its "
            f"own, and persistence.custom names {len(missing)} that this container does not "
            f"hold:\n{named}\nRegister each of them as a service — an application's own "
            "bundle's load_extension, or a scanned @service class — or choose another "
            "persistence.",
        )


def _register_in_memory(
    config: OAuth2ServerConfig,
    services: ServiceConfigurator,
) -> None:
    """Keep everything in this process, forgotten when it ends."""
    _ = services.set(InMemoryClientManager)
    services.alias(ClientManagerInterface, InMemoryClientManager)
    _ = services.set(InMemoryAccessTokenManager).set_argument(
        "persist_access_token",
        config.authorization_server.persist_access_token,
    )
    services.alias(AccessTokenManagerInterface, InMemoryAccessTokenManager)
    _ = services.set(InMemoryRefreshTokenManager)
    services.alias(RefreshTokenManagerInterface, InMemoryRefreshTokenManager)
    _ = services.set(InMemoryAuthorizationCodeManager)
    services.alias(AuthorizationCodeManagerInterface, InMemoryAuthorizationCodeManager)
    _ = services.set(InMemoryDeviceCodeManager)
    services.alias(DeviceCodeManagerInterface, InMemoryDeviceCodeManager)
