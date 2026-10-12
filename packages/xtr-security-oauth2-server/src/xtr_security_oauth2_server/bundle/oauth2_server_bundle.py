"""The bundle wiring this package's authorization server into an application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from typing_extensions import override
from xtr_dependency_injection import Bundle, as_bundle, bundle_active, required_bundle
from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface

from ._command_wiring import configure_commands, register_commands
from ._endpoint_wiring import register_controllers, register_listeners
from ._parameters import (
    ACCESS_TOKEN_TTL_DEFAULT,
    ENCRYPTION_KEY,
    ENCRYPTION_KEY_TYPE,
    SCOPES_DEFAULT,
)
from ._persistence_wiring import PersistenceWiring
from ._service_wiring import (
    register_access_token_saving,
    register_grants,
    register_repositories,
    register_response_type,
    register_scopes,
    register_servers,
    register_signing,
)
from .encryption_key_pass import EncryptionKeyPass
from .grant_type_pass import GRANT_TAG, GrantTypePass
from .metadata_pass import MetadataPass
from .oauth2_server_config import OAuth2ServerConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["OAuth2ServerBundle"]

OAUTH2_SERVER_CHANNEL: Final = "oauth2_server"
"""The logging channel this server writes to.

One line is written on it: an authorization request that arrived with no
resource owner authenticated, which a client is never told the cause of.
"""

#: The passes run after every bundle's own ``process``, so what they read — the
#: encryption key, the tagged grants, the tagged contributors — is final. The
#: mappings pass runs there too, so that a database persistence with no ORM
#: bundle to read it through is reported by the refusal this bundle writes
#: rather than by the pass failing to find a connection.
_PASS_PRIORITY = -10100


@final
@required_bundle("xtr_security.bundle:SecurityBundle")
@required_bundle("xtr_clock.bundle:ClockBundle")
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle")
@required_bundle("xtr_http_kernel.bundle:HttpKernelBundle")
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("oauth2_server", config=OAuth2ServerConfig)
class OAuth2ServerBundle(Bundle[OAuth2ServerConfig]):
    """Turns an :class:`OAuth2ServerConfig` into a working authorization server.

    Listing this bundle brings the security family, the clock, the event
    dispatcher and the HTTP kernel along: tokens are stamped against the
    clock, every decision point is announced on the dispatcher, the endpoints
    are served through the kernel's messages, and the firewall key ``oauth2``
    is opened on the security configuration.

    It builds and boots with no configuration at all, so a fresh application
    still runs its console and can mint the key and register the clients it is
    missing. Nothing is read while it builds: an authorization server signs
    with a key only the deployment holds, says who it is in every token, knows
    a vocabulary of scopes and reads its clients from a store somebody chose,
    and each of those is reported by the service that cannot be built without
    it — an
    :class:`~xtr_security_oauth2_server.exception.InvalidConfigurationError`
    naming the setting and the file it belongs in. Nothing is ever minted on
    the application's behalf.

    What each half of a deployment is made of lives beside this: the stores in
    ``_persistence_wiring``, the protocol engine in ``_service_wiring``, the
    endpoints in ``_endpoint_wiring``, and — only where a console is — the
    commands in ``_command_wiring``.
    """

    __slots__ = ("_persistence",)

    def __init__(self) -> None:
        """Hold the persistence wiring, which spans three of the hooks below."""
        self._persistence = PersistenceWiring()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register the passes, and tag every class that is nominally a grant."""
        builder.add_compiler_pass(EncryptionKeyPass(), priority=_PASS_PRIORITY)
        builder.add_compiler_pass(GrantTypePass(), priority=_PASS_PRIORITY)
        builder.add_compiler_pass(MetadataPass(), priority=_PASS_PRIORITY)
        # A grant an application registers needs nothing written to be run.
        _ = builder.register_for_autoconfiguration(GrantTypeInterface).add_tag(GRANT_TAG)
        mappings = self._persistence.mappings_pass()
        if mappings is not None:
            builder.add_compiler_pass(mappings, priority=_PASS_PRIORITY)

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Open the firewall key ``oauth2``, and declare this server's logging channel."""
        from xtr_security.bundle import (  # noqa: PLC0415 -- an active security bundle pulls this one in
            add_authenticator_factory,
        )

        from xtr_security_oauth2_server.factory.oauth2_factory import (  # noqa: PLC0415 -- imported where it is used, beside the security helper
            OAuth2Factory,
        )

        builder.prepend_extension_config("security", add_authenticator_factory(OAuth2Factory()))
        if bundle_active(builder, "logging"):
            builder.prepend_extension_config("logging", _add_server_channel)

    @override
    def load_extension(
        self,
        config: OAuth2ServerConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register everything this deployment's authorization server is made of.

        Nothing here reads a key, an issuer or a store. Every setting only the
        deployment can supply is read where it is used, so this registers a
        working server and an undescribed one alike.
        """
        server = config.authorization_server
        # Never asked whether it is empty: a key a deployment reads out of its
        # environment arrives here as a placeholder the variable is read for
        # when a server is built, and asking such a value a question about
        # itself is what it cannot answer. Unset is ``None``, and the server
        # asked for reports the setting.
        key = server.encryption_key
        builder.set_parameter(ENCRYPTION_KEY, key if key is not None else "")
        builder.set_parameter(ENCRYPTION_KEY_TYPE, server.encryption_key_type)
        builder.set_parameter(ACCESS_TOKEN_TTL_DEFAULT, server.access_token_ttl)
        builder.set_parameter(SCOPES_DEFAULT, config.scopes.default)
        register_signing(config, services)
        register_access_token_saving(config, services)
        self._persistence.register(config, services, builder)
        register_repositories(services)
        register_scopes(config, services)
        register_grants(config, services)
        register_response_type(config, services)
        register_servers(config, services)
        register_controllers(
            config,
            services,
            OAUTH2_SERVER_CHANNEL if bundle_active(builder, "logging") else None,
        )
        register_listeners(config, services)
        if bundle_active(builder, "console"):
            register_commands(services)

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Hand the commands their settings, and refuse a persistence nothing can serve.

        Raises:
            InvalidConfigurationError: When this deployment keeps its clients
                and credentials in a database and the ORM bundle is not active,
                so nothing would build the connection they live on; or when it
                named its own stores and one of them is not a registered
                service.
        """
        configure_commands(builder)
        self._persistence.refuse_what_nothing_can_serve(builder)


def _add_server_channel(config: object) -> object:
    """Declare this server's channel through the logging config's own ``with_channels``.

    Duck-typed: this package depends on the logging contracts only, never on
    the logging implementation, so it asks the config it is handed rather than
    importing its type.
    """
    with_channels = cast("Callable[[str], object] | None", getattr(config, "with_channels", None))

    return with_channels(OAUTH2_SERVER_CHANNEL) if with_channels is not None else config
