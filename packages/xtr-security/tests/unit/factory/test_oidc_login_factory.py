"""The OIDC login factory builds the provider services and the login."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast, final

import pytest
from joserfc.jwk import KeySet, RSAKey
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core import TokenStorage
from xtr_security_core.user.user_provider_interface import UserProviderInterface

from xtr_security.bundle import (
    OidcBackChannelLogoutConfig,
    OidcEndSessionConfig,
    OidcLoginConfig,
    OidcTokenGeneratorConfig,
    TokenEndpointAuthMethod,
    firewall_dispatcher_name,
)
from xtr_security.exception import InvalidConfigurationError
from xtr_security.factory import AuthenticatorFactoryInterface, OidcLoginFactory
from xtr_security.factory.oidc_login_factory import oidc_token_refresh_listener_name

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Hashable, Mapping

    from xtr_dependency_injection import ServiceKey
    from xtr_security_http.oidc import OidcDiscovery

pytestmark = pytest.mark.anyio


def _login(  # noqa: PLR0913 -- a test helper gathering one login's knobs
    *,
    token_endpoint_auth_method: TokenEndpointAuthMethod = (
        "client_secret_basic"  # noqa: S107 -- a method name, not a secret
    ),
    client_secret: str | None = "secret",  # noqa: S107 -- a stand-in, not a credential
    client_authentication_keyset: str | None = None,
    certificate_options: Mapping[str, str] | None = None,
    signature_verifier_algorithms: tuple[str, ...] | None = None,
    token_generator: OidcTokenGeneratorConfig | None = None,
    backchannel_logout: OidcBackChannelLogoutConfig | None = None,
    end_session: OidcEndSessionConfig | None = None,
) -> OidcLoginConfig:
    """A login against a stand-in provider, carrying the usual secret."""
    return OidcLoginConfig(
        issuer="https://issuer.example",
        client_id="shop",
        client_secret=client_secret,
        token_endpoint_auth_method=token_endpoint_auth_method,
        client_authentication_keyset=client_authentication_keyset,
        certificate_options=certificate_options,
        signature_verifier_algorithms=signature_verifier_algorithms,
        token_generator=token_generator,
        backchannel_logout=backchannel_logout,
        end_session=end_session,
    )


def _generator(key: RSAKey) -> OidcTokenGeneratorConfig:
    """A generator signing with ``key``."""
    return OidcTokenGeneratorConfig(
        algorithms=("RS256",),
        keyset=json.dumps(KeySet([key]).as_dict(private=True)),
        audience="shop-api",
        issuers=("https://issuer.example",),
    )


def _async(target: Callable[..., object]) -> Callable[..., Awaitable[object]]:
    """Narrow a registered factory the container would await."""
    return cast("Callable[..., Awaitable[object]]", target)


@final
class _RecordingDefinition:
    """A stand-in definition handing back its key and recording the tags it gains."""

    def __init__(self, key: ServiceKey, tags: list[tuple[str, dict[str, object]]]) -> None:
        self.key = key
        self._tags = tags

    def add_tag(self, name: str, **attributes: object) -> _RecordingDefinition:
        self._tags.append((name, dict(attributes)))
        return self

    def set_argument(self, name: str, value: object, /) -> _RecordingDefinition:
        del name, value
        return self


@final
class _RecordingConfigurator:
    """A stand-in configurator recording every ``set``, ``alias`` and tag the factory makes."""

    def __init__(self) -> None:
        self.by_qualifier: dict[Hashable, Callable[..., object]] = {}
        self.aliases: list[tuple[type, Hashable]] = []
        self.registered: list[tuple[Hashable, Callable[..., object]]] = []
        self.tags: dict[Hashable | None, list[tuple[str, dict[str, object]]]] = {}

    def set(
        self,
        target: Callable[..., object],
        /,
        *,
        qualifier: Hashable | None = None,
        lifetime: object | None = None,
    ) -> _RecordingDefinition:
        del lifetime
        self.by_qualifier[qualifier] = target
        self.registered.append((qualifier, target))
        tags: list[tuple[str, dict[str, object]]] = []
        self.tags[qualifier] = tags
        return _RecordingDefinition(cast("ServiceKey", (object, qualifier)), tags)

    def alias(
        self,
        alias_type: type,
        target_type: type,
        /,
        *,
        alias_qualifier: Hashable | None = None,
        target_qualifier: Hashable | None = None,
    ) -> None:
        del target_type, target_qualifier
        self.aliases.append((alias_type, alias_qualifier))


def test_it_carries_its_interface_key_and_config() -> None:
    factory = OidcLoginFactory()

    assert AuthenticatorFactoryInterface in type(factory).__mro__
    assert factory.key == "oidc_login"
    assert factory.config_type is OidcLoginConfig
    assert isinstance(factory.priority, int)
    assert factory.entry_point_kind(_login()) == "real"


def test_a_login_without_a_user_provider_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = OidcLoginFactory().create_authenticator(
            _RecordingConfigurator(),  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
            "api",
            _login(),
            None,
        )


def _create(config: OidcLoginConfig) -> _RecordingConfigurator:
    """Run the factory over ``config`` and return what it registered."""
    services = _RecordingConfigurator()
    _ = OidcLoginFactory().create_authenticator(
        services,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        None,  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]
        "api",
        config,
        (UserProviderInterface, "users"),
    )
    return services


def test_it_registers_every_provider_service_the_login_needs() -> None:
    services = _create(_login(signature_verifier_algorithms=("RS256",)))

    assert "api#oidc_discovery" in services.by_qualifier
    assert "api#oidc_id_token" in services.by_qualifier
    assert "api#oidc_signature_verifier" in services.by_qualifier
    assert "api#oidc_client" in services.by_qualifier
    assert "api#oidc_token_refresher" in services.by_qualifier
    assert oidc_token_refresh_listener_name("api") in services.by_qualifier
    assert "api#oidc_success_handler" in services.by_qualifier
    assert "api#oidc_failure_handler" in services.by_qualifier
    assert "api" in services.by_qualifier
    assert "api#oidc_token_generator" not in services.by_qualifier
    from xtr_security_http import FirewallListenerInterface

    assert (FirewallListenerInterface, oidc_token_refresh_listener_name("api")) in services.aliases


def test_no_verifier_is_registered_without_algorithms() -> None:
    services = _create(_login())

    assert "api#oidc_signature_verifier" not in services.by_qualifier


def test_a_configured_generator_registers_under_the_firewalls_name() -> None:
    key = RSAKey.generate_key(2048)
    services = _create(_login(token_generator=_generator(key)))

    from xtr_security_http.access_token.oidc import OidcTokenGenerator

    # The generator registers under the firewall's own name — the qualifier
    # the token-generate command collects its generators by — beside the
    # authenticator, which carries the same qualifier under its own type.
    registered = [target for qualifier, target in services.registered if qualifier == "api"]
    assert len(registered) == 2
    generator = next(
        target
        for target in registered
        if target.__annotations__.get("return") is OidcTokenGenerator
    )

    built = generator(clock=None)
    assert isinstance(built, OidcTokenGenerator)
    token = built.generate("alice")
    assert isinstance(token, str)
    assert token


async def test_the_registered_factories_build_the_real_services() -> None:
    from xtr_security_http import HttpUtils, OidcTokenRefreshListener
    from xtr_security_http.authentication import (
        DefaultAuthenticationFailureHandler,
        DefaultAuthenticationSuccessHandler,
    )
    from xtr_security_http.authenticator.oidc_login_authenticator import OidcLoginAuthenticator
    from xtr_security_http.oidc import (
        OidcClient,
        OidcDiscovery,
        OidcIdToken,
        OidcSignatureVerifier,
        OidcTokenRefresher,
    )

    services = _create(_login(signature_verifier_algorithms=("RS256",)))
    http_utils = HttpUtils(ResponseFactory())
    provider = cast("UserProviderInterface", object())
    discovery = services.by_qualifier["api#oidc_discovery"]()
    id_token = services.by_qualifier["api#oidc_id_token"](clock=None)
    verifier = services.by_qualifier["api#oidc_signature_verifier"](discovery=discovery, clock=None)
    client = await _async(services.by_qualifier["api#oidc_client"])(
        discovery=discovery,
        clock=None,
    )
    refresher = services.by_qualifier["api#oidc_token_refresher"](
        client=client,
        discovery=discovery,
        id_token=id_token,
        clock=None,
        verifier=verifier,
    )
    listener = services.by_qualifier[oidc_token_refresh_listener_name("api")](
        storage=TokenStorage(),
        refresher=refresher,
    )
    success = services.by_qualifier["api#oidc_success_handler"](http_utils=http_utils)
    failure = services.by_qualifier["api#oidc_failure_handler"](http_utils=http_utils)
    authenticator = await _async(services.by_qualifier["api"])(
        http_utils=http_utils,
        provider=provider,
        client=client,
        discovery=discovery,
        id_token=id_token,
        success=success,
        failure=failure,
        clock=None,
        verifier=verifier,
        dispatcher=None,
    )

    assert isinstance(discovery, OidcDiscovery)
    assert isinstance(id_token, OidcIdToken)
    assert isinstance(verifier, OidcSignatureVerifier)
    assert isinstance(client, OidcClient)
    assert isinstance(refresher, OidcTokenRefresher)
    assert isinstance(listener, OidcTokenRefreshListener)
    assert isinstance(success, DefaultAuthenticationSuccessHandler)
    assert isinstance(failure, DefaultAuthenticationFailureHandler)
    assert isinstance(authenticator, OidcLoginAuthenticator)


async def test_the_client_authenticates_by_the_configured_method() -> None:
    """A secret-bearing method builds the client without touching the provider."""
    services = _create(_login(token_endpoint_auth_method="client_secret_post"))

    client = await _async(services.by_qualifier["api#oidc_client"])(
        discovery=cast("OidcDiscovery", object()),
        clock=None,
    )

    from xtr_security_http.oidc import OidcClient

    assert isinstance(client, OidcClient)


@final
class _AnnouncingDiscovery:
    """A stand-in discovery announcing its issuer to the assertion methods."""

    async def get_issuer(self) -> str:
        return "https://issuer.example"


async def test_the_assertion_methods_sign_for_the_announced_issuer() -> None:
    """The JWT-bearing methods build their assertion from the discovery's issuer."""
    from xtr_security_http.oauth2.client_authentication.client_secret_jwt import (
        ClientSecretJwt,
    )
    from xtr_security_http.oidc import OidcClient

    # The JWT-bearing method signs with the secret as its key, which the
    # length guard wants at least 32 bytes of.
    services = _create(
        _login(token_endpoint_auth_method="client_secret_jwt", client_secret="s" * 32)
    )

    client = await _async(services.by_qualifier["api#oidc_client"])(
        discovery=_AnnouncingDiscovery(),
        clock=None,
    )

    assert isinstance(client, OidcClient)
    assert isinstance(client._client_authentication, ClientSecretJwt)


async def test_private_key_jwt_signs_with_the_configured_key() -> None:
    """The private-key method builds its assertion from the configured key set."""
    import json as _json

    from joserfc.jwk import KeySet as JoserfcKeySet
    from xtr_security_http.oauth2.client_authentication.private_key_jwt import (
        PrivateKeyJwt,
    )
    from xtr_security_http.oidc import OidcClient

    key = RSAKey.generate_key(2048, parameters={"kid": "k1"})
    services = _create(
        _login(
            token_endpoint_auth_method="private_key_jwt",
            client_authentication_keyset=_json.dumps(JoserfcKeySet([key]).as_dict(private=True)),
        )
    )

    client = await _async(services.by_qualifier["api#oidc_client"])(
        discovery=_AnnouncingDiscovery(),
        clock=None,
    )

    assert isinstance(client, OidcClient)
    assert isinstance(client._client_authentication, PrivateKeyJwt)


async def test_the_tls_methods_carry_their_certificate_on_the_client() -> None:
    """The TLS pair builds with no arguments; the certificate rides the client."""
    from xtr_security_http.oauth2.client_authentication.self_signed_tls_client_auth import (
        SelfSignedTlsClientAuth,
    )
    from xtr_security_http.oauth2.client_authentication.tls_client_auth import (
        TlsClientAuth,
    )
    from xtr_security_http.oidc import OidcClient

    tls = _create(
        _login(
            token_endpoint_auth_method="tls_client_auth",
            client_secret=None,
            certificate_options={"local_cert": "cert.pem", "local_pk": "key.pem"},
        )
    )
    self_signed = _create(
        _login(token_endpoint_auth_method="self_signed_tls_client_auth", client_secret=None)
    )

    tls_client = await _async(tls.by_qualifier["api#oidc_client"])(
        discovery=_AnnouncingDiscovery(),
        clock=None,
    )
    self_signed_client = await _async(self_signed.by_qualifier["api#oidc_client"])(
        discovery=_AnnouncingDiscovery(),
        clock=None,
    )

    assert isinstance(tls_client, OidcClient)
    assert isinstance(tls_client._client_authentication, TlsClientAuth)
    assert isinstance(self_signed_client, OidcClient)
    assert isinstance(
        self_signed_client._client_authentication,
        SelfSignedTlsClientAuth,
    )


async def test_a_public_client_authenticates_with_nothing() -> None:
    """The public method builds the client with no endpoint authentication."""
    from xtr_security_http.oauth2.client_authentication import NoClientAuthentication
    from xtr_security_http.oidc import OidcClient

    services = _create(_login(token_endpoint_auth_method="none", client_secret=None))

    client = await _async(services.by_qualifier["api#oidc_client"])(
        discovery=_AnnouncingDiscovery(),
        clock=None,
    )

    assert isinstance(client, OidcClient)
    assert isinstance(client._client_authentication, NoClientAuthentication)


def _handler_factories(services: _RecordingConfigurator) -> list[object]:
    """Return the factories building the back-channel logout handler."""
    from xtr_security.oidc_back_channel_logout_handler import OidcBackChannelLogoutHandler

    return [
        factory
        for _qualifier, factory in services.registered
        if factory.__annotations__.get("return") is OidcBackChannelLogoutHandler
    ]


def test_a_backchannel_logout_registers_its_services_and_listener() -> None:
    from xtr_security_http import CheckRefreshedUserEvent

    services = _create(
        _login(
            signature_verifier_algorithms=("RS256",),
            backchannel_logout=OidcBackChannelLogoutConfig(route="/logout/provider"),
        )
    )

    assert "api#oidc_ended_sessions" in services.by_qualifier
    assert "api#oidc_logout_token" in services.by_qualifier
    assert "api#oidc_back_channel_logout" in services.by_qualifier
    assert len(_handler_factories(services)) == 1
    assert "api#oidc_back_channel_logout_listener" in services.by_qualifier
    assert services.tags["api#oidc_back_channel_logout_listener"] == [
        ("event_dispatcher.listener", {"event": CheckRefreshedUserEvent})
    ]


def test_a_backchannel_logout_without_a_verifier_fails_the_build() -> None:
    with pytest.raises(InvalidConfigurationError, match="signature_verifier_algorithms"):
        _ = _create(_login(backchannel_logout=OidcBackChannelLogoutConfig()))


def test_no_backchannel_services_register_without_the_block() -> None:
    services = _create(_login(signature_verifier_algorithms=("RS256",)))

    assert "api#oidc_ended_sessions" not in services.by_qualifier
    assert "api#oidc_back_channel_logout_listener" not in services.by_qualifier
    assert _handler_factories(services) == []


def test_a_disabled_backchannel_logout_registers_nothing() -> None:
    services = _create(
        _login(
            signature_verifier_algorithms=("RS256",),
            backchannel_logout=OidcBackChannelLogoutConfig(enable=False),
        )
    )

    assert "api#oidc_ended_sessions" not in services.by_qualifier
    assert _handler_factories(services) == []


def test_an_end_session_listener_subscribes_on_the_firewalls_dispatcher() -> None:
    services = _create(
        _login(
            end_session=OidcEndSessionConfig(post_logout_redirect_path="/bye"),
        )
    )

    assert "api#oidc_end_session_listener" in services.by_qualifier
    assert services.tags["api#oidc_end_session_listener"] == [
        (
            "event_dispatcher.subscriber",
            {"dispatcher": firewall_dispatcher_name("api")},
        )
    ]


def test_no_end_session_listener_registers_without_the_block() -> None:
    services = _create(_login())

    assert "api#oidc_end_session_listener" not in services.by_qualifier
