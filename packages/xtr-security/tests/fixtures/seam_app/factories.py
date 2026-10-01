"""The fake third-party factories and configs the seam bundle prepends.

An authenticator factory (key ``fake_oauth2``) that builds a bearer authenticator
around a fake handler, and a token-handler factory (key ``fake_handler``) — both
implementing the family's factory interfaces without the family knowing them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_security_core import InMemoryUser
from xtr_security_core.user.user_interface import UserInterface
from xtr_security_http import (
    AccessTokenAuthenticator,
    HeaderAccessTokenExtractor,
    UserBadge,
)
from xtr_security_http.access_token.access_token_handler_interface import (
    AccessTokenHandlerInterface,
)
from xtr_security_http.exception import InvalidAccessTokenError

# The container keys the handler and authenticator factories by their return type.
from xtr_service_contracts import ContainerInterface

from xtr_security.bundle import (
    AuthenticatorFactoryInterface,
    TokenHandlerFactoryInterface,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

__all__ = [
    "FakeHandlerConfig",
    "FakeOAuth2Config",
    "FakeOAuth2Factory",
    "FakeTokenHandler",
    "FakeTokenHandlerFactory",
]


@dataclass(frozen=True, slots=True)
class FakeHandlerConfig:
    """The configuration the fake token-handler factory builds from."""

    type: str = "fake_handler"


@dataclass(frozen=True, slots=True)
class FakeOAuth2Config:
    """The configuration the fake authenticator factory builds from."""

    token_handler: object = None
    realm: str | None = None


@final
class FakeTokenHandler(AccessTokenHandlerInterface):
    """A fake handler: ``granted`` proves a scoped user, anything else fails."""

    __slots__ = ()

    @override
    async def get_user_badge_from(self, access_token: str) -> UserBadge:
        """Return a badge for the fake's one good token.

        Raises:
            InvalidAccessTokenError: For any token but ``granted``.
        """
        if access_token != "granted":
            raise InvalidAccessTokenError("The fake token is not known.")

        def load(identifier: str) -> UserInterface:
            return InMemoryUser(identifier, roles=["ROLE_USER"])

        return UserBadge("carol", user_loader=load, attributes={"scope": ["fake:read"]})


@final
class FakeTokenHandlerFactory(TokenHandlerFactoryInterface):
    """Builds the fake token handler; registered through the token-handler seam."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "fake_handler"

    @property
    @override
    def config_type(self) -> type:
        return FakeHandlerConfig

    @override
    def create(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        service_id: str,
        config: object,
    ) -> ServiceKey:
        del builder, config

        def fake_token_handler() -> FakeTokenHandler:
            return FakeTokenHandler()

        fake_token_handler.__name__ = f"fake_token_handler_{service_id}"
        fake_token_handler.__qualname__ = fake_token_handler.__name__
        return services.set(fake_token_handler, qualifier=service_id).key


@final
class FakeOAuth2Factory(AuthenticatorFactoryInterface):
    """Builds a bearer authenticator around the fake handler; the ``fake_oauth2`` seam."""

    __slots__ = ()

    @property
    @override
    def key(self) -> str:
        return "fake_oauth2"

    @property
    @override
    def priority(self) -> int:
        return 50

    @property
    @override
    def config_type(self) -> type:
        return FakeOAuth2Config

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        del user_provider
        settings = cast("FakeOAuth2Config", config)
        realm = settings.realm

        async def fake_authenticator(container: ContainerInterface) -> AccessTokenAuthenticator:
            handler = await container.get(FakeTokenHandler, f"{firewall_name}_fake_handler")
            return AccessTokenAuthenticator(
                handler,
                HeaderAccessTokenExtractor(),
                realm=realm,
            )

        fake_authenticator.__name__ = f"fake_authenticator_{firewall_name}"
        fake_authenticator.__qualname__ = fake_authenticator.__name__
        _ = FakeTokenHandlerFactory().create(
            services,
            builder,
            f"{firewall_name}_fake_handler",
            FakeHandlerConfig(),
        )
        return (services.set(fake_authenticator, qualifier=firewall_name, lifetime="scoped").key,)
