"""The factory that builds a bearer access-token authenticator for a firewall."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override

# These annotate factory parameters and returns the container reads at runtime,
# so the marker, the qualifier helper and the return types stay importable here.
from xtr_dependency_injection import Target, named_factory
from xtr_security_http import (
    AccessTokenAuthenticator,
    ChainAccessTokenExtractor,
    FormEncodedBodyExtractor,
    HeaderAccessTokenExtractor,
    QueryAccessTokenExtractor,
)
from xtr_security_http.access_token.access_token_extractor_interface import (  # noqa: TC002
    AccessTokenExtractorInterface,
)

from xtr_security.bundle.authenticator_configs import AccessTokenConfig
from xtr_security.exception import InvalidConfigurationError

from .authenticator_factory_interface import AuthenticatorFactoryInterface

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator, ServiceKey
    from xtr_security_core.user.user_provider_interface import UserProviderInterface
    from xtr_security_http.access_token.access_token_handler_interface import (
        AccessTokenHandlerInterface,
    )

    from xtr_security.access_token.token_handler_factory_interface import (
        TokenHandlerFactoryInterface,
    )

__all__ = ["AccessTokenFactory"]

_EXTRACTOR_PRIORITY = 100


@final
class AccessTokenFactory(AuthenticatorFactoryInterface):
    """Builds an :class:`~xtr_security_http.AccessTokenAuthenticator` from configuration.

    The token handler is built through the token-handler factory registry the
    bundle hands this factory (seam S-2): the configured handler's ``type``
    selects a token-handler factory, which registers the handler service. The
    named extractors become the extractor the authenticator reads tokens with,
    chained when more than one. The authenticator is registered as a factory so
    it can pull the handler, the extractor and the firewall's user provider from
    the container.
    """

    __slots__ = ("_token_handler_factories",)

    def __init__(
        self,
        token_handler_factories: Mapping[str, TokenHandlerFactoryInterface] | None = None,
    ) -> None:
        """Record the token-handler factories, keyed by their configuration type."""
        self._token_handler_factories = dict(token_handler_factories or {})

    @property
    @override
    def key(self) -> str:
        """Name this kind of authenticator ``access_token``."""
        return "access_token"

    @property
    @override
    def priority(self) -> int:
        """Run at the default priority; other authenticators order around it."""
        return _EXTRACTOR_PRIORITY

    @property
    @override
    def config_type(self) -> type:
        """Build instances of :class:`AccessTokenConfig`."""
        return AccessTokenConfig

    def with_token_handler_factories(
        self,
        token_handler_factories: Mapping[str, TokenHandlerFactoryInterface],
    ) -> AccessTokenFactory:
        """Return a copy that resolves token handlers through ``token_handler_factories``."""
        return AccessTokenFactory(token_handler_factories)

    @override
    def create_authenticator(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        config: object,
        user_provider: ServiceKey | None,
    ) -> Sequence[ServiceKey]:
        """Register the token handler, the extractor and the authenticator."""
        settings = cast("AccessTokenConfig", config)
        handler_key = self._build_handler(services, builder, firewall_name, settings)
        extractor_key = self._build_extractor(services, firewall_name, settings)
        authenticator = _authenticator_factory(
            firewall_name,
            handler_key,
            extractor_key,
            user_provider,
            settings.realm,
        )
        key = services.set(authenticator, qualifier=firewall_name).key
        return (key,)

    def _build_handler(
        self,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        firewall_name: str,
        settings: AccessTokenConfig,
    ) -> ServiceKey:
        """Build the token handler through the factory its configuration names."""
        handler_config = settings.token_handler
        handler_type = getattr(handler_config, "type", None)
        for factory in self._token_handler_factories.values():
            if isinstance(handler_config, factory.config_type):
                return factory.create(
                    services,
                    builder,
                    f"{firewall_name}_{factory.key}",
                    handler_config,
                )
        raise InvalidConfigurationError(
            f'No token-handler factory handles the configuration "{handler_type}" '
            f'on the firewall "{firewall_name}".',
        )

    def _build_extractor(
        self,
        services: ServiceConfigurator,
        firewall_name: str,
        settings: AccessTokenConfig,
    ) -> ServiceKey:
        """Build the extractor, chaining the named extractors when more than one."""
        factory = named_factory(
            _extractor_factory(settings.token_extractors),
            f"access_token_extractor_{firewall_name}",
        )
        return services.set(factory, qualifier=firewall_name).key


def _extractor_factory(
    names: tuple[str, ...],
) -> Callable[[], AccessTokenExtractorInterface]:
    """Return a factory building the extractor the named extractors describe."""

    def access_token_extractor() -> AccessTokenExtractorInterface:
        extractors = [_one_extractor(name) for name in names]
        if len(extractors) == 1:
            return extractors[0]
        return ChainAccessTokenExtractor(extractors)

    return access_token_extractor


def _one_extractor(name: str) -> AccessTokenExtractorInterface:
    """Build one extractor from its name."""
    if name == "header":
        return HeaderAccessTokenExtractor()
    if name == "query":
        return QueryAccessTokenExtractor()
    return FormEncodedBodyExtractor()


def _authenticator_factory(
    firewall_name: str,
    handler_key: ServiceKey,
    extractor_key: ServiceKey,
    user_provider: ServiceKey | None,
    realm: str | None,
) -> Callable[..., Awaitable[AccessTokenAuthenticator]]:
    """Return a factory building the access-token authenticator from injected services.

    The handler, the extractor and — when the firewall names one — its user
    provider are each injected by their key with ``Target``, so the factory is
    never handed the whole container.
    """

    async def access_token_authenticator(
        handler: object,
        extractor: object,
        provider: object | None = None,
    ) -> AccessTokenAuthenticator:
        return AccessTokenAuthenticator(
            cast("AccessTokenHandlerInterface", handler),
            cast("AccessTokenExtractorInterface", extractor),
            user_provider=cast("UserProviderInterface | None", provider),
            realm=realm,
        )

    annotations: dict[str, object] = {
        "handler": _qualified(handler_key),
        "extractor": _qualified(extractor_key),
        "return": AccessTokenAuthenticator,
    }
    if user_provider is not None:
        annotations["provider"] = _qualified(user_provider)
    access_token_authenticator.__annotations__ = annotations
    return named_factory(access_token_authenticator, f"authenticator_{firewall_name}")


def _qualified(key: ServiceKey) -> object:
    """Return the injection annotation selecting the service ``key`` names.

    Built at runtime from a service key, so the second type checker reads the
    subscript as a static type expression it is not — hence the suppression; the
    container evaluates it as the marker it forms.
    """
    return Annotated[key[0], Target(key[1])]  # ty: ignore[invalid-type-form] -- runtime marker
