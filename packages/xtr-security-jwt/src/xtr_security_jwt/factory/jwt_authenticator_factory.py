"""The factory that builds a self-issued-token firewall authenticator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

# These annotate factory parameters and returns the container reads at runtime,
# so the marker, the qualifier helper and the return types stay importable here.
from xtr_dependency_injection import Target, named_factory
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security_jwt.bundle.jwt_authenticator_config import JwtAuthenticatorConfig
from xtr_security_jwt.bundle.jwt_config import JwtConfig
from xtr_security_jwt.security.authenticator.jwt_authenticator import JwtAuthenticator
from xtr_security_jwt.services.jwt_token_manager_interface import (
    JwtTokenManagerInterface,
)
from xtr_security_jwt.token_extractor.authorization_header_token_extractor import (
    AuthorizationHeaderTokenExtractor,
)
from xtr_security_jwt.token_extractor.chain_token_extractor import ChainTokenExtractor
from xtr_security_jwt.token_extractor.cookie_token_extractor import CookieTokenExtractor
from xtr_security_jwt.token_extractor.query_parameter_token_extractor import (
    QueryParameterTokenExtractor,
)
from xtr_security_jwt.token_extractor.split_cookie_extractor import SplitCookieExtractor

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey

    from xtr_security_jwt.bundle.token_extractors_configs import TokenExtractorsConfig
    from xtr_security_jwt.token_extractor.token_extractor_interface import TokenExtractorInterface

__all__ = ["JwtAuthenticatorFactory"]

#: Where the JWT authenticator sits in a firewall's order.
_JWT_PRIORITY = 100


@final
class JwtAuthenticatorFactory:
    """Builds a :class:`~xtr_security_jwt.security.authenticator.JwtAuthenticator` for a firewall.

    Registered onto the security bundle's authenticator registry under the key
    ``jwt``. A firewall names a
    :class:`~xtr_security_jwt.bundle.JwtAuthenticatorConfig`; this factory
    registers the token extractor the bundle's configuration describes and an
    authenticator over the token manager, the firewall's own event dispatcher,
    that extractor and the firewall's user provider — nothing beyond the firewall
    key to write.
    """

    __slots__ = ()

    @property
    def key(self) -> str:
        """Name this kind of authenticator ``jwt``."""
        return "jwt"

    @property
    def priority(self) -> int:
        """Run at the default bearer priority; other authenticators order around it."""
        return _JWT_PRIORITY

    @property
    def config_type(self) -> type:
        """Build instances of :class:`JwtAuthenticatorConfig`."""
        return JwtAuthenticatorConfig

    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the token extractor and the self-issued-token authenticator."""
        del builder, config
        extractor_key = _register_extractor(services, firewall_name)
        authenticator = _authenticator_factory(firewall_name, extractor_key, user_provider)
        key = services.set(authenticator, qualifier=firewall_name, lifetime="scoped").key
        return (key,)


def _register_extractor(services: ServiceConfigurator, firewall_name: str) -> ServiceKey:
    """Register the token extractor built from the bundle's extractor configuration."""
    factory = named_factory(_extractor_factory(), f"jwt_token_extractor_{firewall_name}")
    return services.set(factory, qualifier=firewall_name).key


def _extractor_factory() -> Callable[..., TokenExtractorInterface]:
    """Return a factory building the extractor the bundle's configuration describes.

    The container reads the factory's parameter and return annotations at runtime
    to key the service, so both are set as real types rather than left under a
    string it cannot evaluate.
    """

    def jwt_token_extractor(config: JwtConfig) -> TokenExtractorInterface:
        extractors = _extractors_from(config.token_extractors)
        if len(extractors) == 1:
            return extractors[0]
        return ChainTokenExtractor(extractors)

    jwt_token_extractor.__annotations__ = {
        "config": JwtConfig,
        "return": _token_extractor_interface(),
    }
    return jwt_token_extractor


def _token_extractor_interface() -> type:
    """Return the extractor interface, imported at runtime for the container to read."""
    from xtr_security_jwt.token_extractor.token_extractor_interface import (  # noqa: PLC0415
        TokenExtractorInterface as _TokenExtractorInterface,
    )

    return _TokenExtractorInterface


def _extractors_from(config: TokenExtractorsConfig) -> list[TokenExtractorInterface]:
    """Build, in the reference's fixed order, every extractor the configuration enables."""
    extractors: list[TokenExtractorInterface] = []
    header = config.authorization_header
    if header.enabled:
        extractors.append(AuthorizationHeaderTokenExtractor(header.prefix, header.name))
    if config.query_parameter.enabled:
        extractors.append(QueryParameterTokenExtractor(config.query_parameter.name))
    if config.cookie.enabled:
        extractors.append(CookieTokenExtractor(config.cookie.name))
    if config.split_cookie.enabled:
        extractors.append(SplitCookieExtractor(config.split_cookie.cookies))
    if not extractors:
        extractors.append(AuthorizationHeaderTokenExtractor())
    return extractors


def _authenticator_factory(
    firewall_name: str,
    extractor_key: ServiceKey,
    user_provider: ServiceKey | None,
) -> Callable[..., Awaitable[JwtAuthenticator]]:
    """Return a factory building the authenticator from injected services.

    The token manager, the main event dispatcher — the JWT events are the
    application's to hear, whichever firewall raised them — the extractor and
    the firewall's user provider are each injected by their type or key, so the
    factory is never handed the whole container.
    """

    async def jwt_authenticator(
        manager: JwtTokenManagerInterface,
        dispatcher: EventDispatcherInterface,
        extractor: object,
        provider: UserProviderInterface,
    ) -> JwtAuthenticator:
        return JwtAuthenticator(
            manager,
            dispatcher,
            cast("TokenExtractorInterface", extractor),
            provider,
        )

    jwt_authenticator.__annotations__ = {
        "manager": JwtTokenManagerInterface,
        "dispatcher": EventDispatcherInterface,
        "extractor": _qualified(extractor_key),
        "provider": _qualified(user_provider)
        if user_provider is not None
        else UserProviderInterface,
        "return": JwtAuthenticator,
    }
    return named_factory(jwt_authenticator, f"jwt_authenticator_{firewall_name}")


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names."""
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker
