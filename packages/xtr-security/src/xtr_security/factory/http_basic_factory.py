"""The factory that builds an HTTP basic authenticator for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_http import (
    HttpBasicAuthenticator,
)

from xtr_security.bundle.authenticator_configs import HttpBasicConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = ["HttpBasicFactory"]


@final
class HttpBasicFactory(AuthenticatorFactoryInterface):
    """Builds an :class:`~xtr_security_http.HttpBasicAuthenticator` from configuration.

    The browser's own credential prompt is the login: the authenticator reads
    the ``Authorization: Basic`` header the request carries and challenges
    with the configured realm when it is absent or wrong. It needs the
    firewall's user provider — the credentials are checked against it — and
    its challenge is a real entry point.
    """

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``http_basic``."""
        return "http_basic"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return 0

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`HttpBasicConfig`."""
        return HttpBasicConfig

    def entry_point_kind(self, config: object) -> str:
        """Answer that the basic challenge is a real entry point."""
        del config
        return "real"

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the authenticator over the firewall's user provider."""
        del builder
        settings = cast("HttpBasicConfig", config)
        if user_provider is None:
            raise InvalidConfigurationError(
                f'An HTTP basic authenticator on the firewall "{firewall_name}" needs a user '
                f"provider; name one on the firewall.",
            )

        def http_basic_authenticator(
            provider: UserProviderInterface,
            responses: ResponseFactoryInterface,
        ) -> HttpBasicAuthenticator:
            return HttpBasicAuthenticator(settings.realm, provider, responses)

        http_basic_authenticator.__annotations__ = {
            "provider": Annotated[UserProviderInterface, Target(user_provider[1])],
            "responses": ResponseFactoryInterface,
            "return": HttpBasicAuthenticator,
        }
        http_basic_authenticator.__name__ = f"http_basic_authenticator_{firewall_name}"
        http_basic_authenticator.__qualname__ = http_basic_authenticator.__name__
        return (services.set(http_basic_authenticator, qualifier=firewall_name).key,)
