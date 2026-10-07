"""The xtr-security-jwt bundle: self-issued tokens on the security family.

Reads a :class:`JwtConfig` and registers the signing and verifying chain — a key
loader, a JWS provider, the encoder and the token manager — and, through the
security family's factory seams, an authenticator keyed ``jwt`` and a
user-provider keyed ``jwt``, so a firewall accepts self-issued tokens by writing
``authenticators=(JwtAuthenticatorConfig(),)``.

This is an add-on bundle: no other bundle requires it, so it only ever arrives by
being listed, and it cannot sign a token without a key the application must
choose. It therefore fails the build when no ``secret_key`` is configured, naming
the missing setting and the ``@configure`` function to write.
"""

from __future__ import annotations

from collections.abc import (
    Hashable,
    Mapping,
)
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override

# The clock, the dispatcher and the collected enrichments annotate factory
# parameters the container reads at runtime, so they cannot hide under
# TYPE_CHECKING.
from xtr_clock import ClockInterface
from xtr_dependency_injection import (
    Bundle,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_event_dispatcher_contracts import (
    EventDispatcherInterface,
)

from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.encoder.jwt_encoder_interface import JwtEncoderInterface
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import (
    JoserfcJwsProvider,
    require_hmac_secret_length,
)
from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface
from xtr_security_jwt.services.key_loader._algorithms import HMAC_ALGORITHMS
from xtr_security_jwt.services.key_loader.key_loader_interface import (
    TYPE_PRIVATE,
    KeyLoaderInterface,
)
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader
from xtr_security_jwt.services.payload_enrichment.chain_enrichment import ChainEnrichment
from xtr_security_jwt.services.payload_enrichment.null_enrichment import NullEnrichment
from xtr_security_jwt.services.payload_enrichment_interface import (
    PayloadEnrichmentInterface,
)

from .jwt_config import JwtConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

__all__ = ["JwtBundle"]

_CONFIGURE_HINT = (
    "Set them in <app>/config/jwt.py with a @configure function returning "
    "JwtConfig(secret_key=..., issuer=...)."
)

#: The tag every payload enrichment carries, so the manager collects them all.
_ENRICHMENT_TAG = "jwt.payload_enrichment"


@final
@required_bundle("xtr_security.bundle:SecurityBundle")
@required_bundle("xtr_clock.bundle:ClockBundle")
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle")
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("jwt", config=JwtConfig)
class JwtBundle(Bundle[JwtConfig]):
    """Registers the self-issued-token services and opens the firewall key ``jwt``.

    Requires the security, clock and event-dispatcher bundles: listing this one
    brings the security family along, and the manager reads its times from the
    clock and announces its events on the dispatcher. It prepends its ``jwt``
    authenticator and user-provider factories onto the security configuration.
    """

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Add the ``jwt`` authenticator and user-provider factories to security."""
        from xtr_security.bundle import (  # noqa: PLC0415 -- an active security bundle pulls this one in
            add_authenticator_factory,
            add_user_provider_factory,
        )

        from xtr_security_jwt.factory.jwt_authenticator_factory import (  # noqa: PLC0415 -- imported where it is used, beside the security helpers
            JwtAuthenticatorFactory,
        )
        from xtr_security_jwt.user_provider.jwt_user_factory import (  # noqa: PLC0415 -- imported where it is used, beside the security helpers
            JwtUserFactory,
        )

        builder.prepend_extension_config(
            "security",
            add_authenticator_factory(JwtAuthenticatorFactory()),
        )
        builder.prepend_extension_config(
            "security",
            add_user_provider_factory(JwtUserFactory()),
        )

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Tag every registered payload enrichment so the manager collects them all."""
        _ = builder.register_for_autoconfiguration(PayloadEnrichmentInterface).add_tag(
            _ENRICHMENT_TAG,
        )

    @override
    def load_extension(
        self,
        config: JwtConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the signing chain, the manager and the commands, or fail the build.

        Raises:
            InvalidConfigurationError: When no signing key or issuer is configured
                — an add-on bundle that cannot work without them — or when an HMAC
                secret is shorter than its algorithm requires.
        """
        self._require_build_settings(config)
        self._require_hmac_secret_length(config)
        _ = services.set(NullEnrichment).add_tag(_ENRICHMENT_TAG)
        _ = services.set(_key_loader_factory(config))
        services.alias(KeyLoaderInterface, RawKeyLoader)
        _ = services.set(_jws_provider_factory(config))
        services.alias(JwsProviderInterface, JoserfcJwsProvider)
        _ = services.set(_encoder_factory())
        services.alias(JwtEncoderInterface, _encoder_service(config))
        _ = services.set(_manager_factory(config))
        services.alias(JwtTokenManagerInterface, JwtManager)
        if bundle_active(builder, "console"):
            services.load("xtr_security_jwt.command.generate_key_pair_command")
            services.load("xtr_security_jwt.command.generate_token_command")
            services.load("xtr_security_jwt.command.check_config_command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Alias every tagged enrichment under a qualifier the manager gathers them by."""
        keys = tuple(builder.find_tagged_service_ids(_ENRICHMENT_TAG))
        qualifiers = tuple(f"jwt_enrichment_{index}" for index in range(len(keys)))
        for qualifier, key in zip(qualifiers, keys, strict=True):
            builder.set_alias(
                PayloadEnrichmentInterface,
                key[0],
                alias_qualifier=qualifier,
                target_qualifier=key[1],
            )
        _ = builder.get_definition(JwtManager).set_argument("enrichment_qualifiers", qualifiers)

    @staticmethod
    def _require_build_settings(config: JwtConfig) -> None:
        """Fail the build when a signing key or an issuer is missing.

        An add-on bundle that mints and verifies self-issued tokens cannot work
        without a signing key to sign with and an issuer to stamp and check, so
        it names both that are missing rather than failing at the first request.

        A plain empty string is as missing as nothing at all, for the key as for
        the issuer: it would reach the key loader as key material, or stamp
        nothing as ``iss``, and fail far from the configuration that wrote it. An
        unresolved ``env()`` placeholder — the form the recipe writes — stands
        for a value read when the manager is built, so it cannot decide anything
        here; it is taken as set, and the manager refuses an empty resolved
        issuer where it is built.

        Raises:
            InvalidConfigurationError: When ``secret_key`` or ``issuer`` is unset.
        """
        from xtr_security.bundle import InvalidConfigurationError  # noqa: PLC0415

        missing: list[str] = []
        if config.secret_key is None or (type(config.secret_key) is str and not config.secret_key):
            missing.append("a signing key (secret_key)")
        if type(config.issuer) is str and not config.issuer:
            missing.append("an issuer (issuer)")
        if missing:
            raise InvalidConfigurationError(
                "The JWT bundle needs "
                + " and ".join(missing)
                + " but none is configured. "
                + _CONFIGURE_HINT,
            )

    @staticmethod
    def _require_hmac_secret_length(config: JwtConfig) -> None:
        """Fail the build when the HMAC secret is shorter than its algorithm requires.

        ``secret_key`` may be the shared secret itself or the path of a file
        holding it, so the floor is applied to the material the key loader
        resolves — the very loader the container will build, asked the way the
        JWS provider asks it — rather than to the configured string. Measuring
        the string would pass a long path naming a five-byte secret and refuse a
        short path naming a long one.

        An unresolved ``env()`` placeholder is left alone: it carries its default,
        not the deployment's secret, and the provider measures the real value as
        it imports the key.

        Raises:
            InvalidConfigurationError: When the resolved secret is too short.
        """
        algorithm = config.encoder.signature_algorithm
        if algorithm not in HMAC_ALGORITHMS or type(config.secret_key) is not str:
            return
        require_hmac_secret_length(algorithm, _key_loader_factory(config)().load_key(TYPE_PRIVATE))


def _key_loader_factory(config: JwtConfig) -> Callable[[], RawKeyLoader]:
    """Return a factory building the key loader from the configured key material."""
    secret_key = config.secret_key
    public_key = config.public_key
    passphrase = config.pass_phrase
    additional = config.additional_public_keys

    def key_loader() -> RawKeyLoader:
        return RawKeyLoader(secret_key, public_key, passphrase or None, additional)

    return key_loader


def _jws_provider_factory(
    config: JwtConfig,
) -> Callable[..., JoserfcJwsProvider]:
    """Return a factory building the JWS provider over the key loader and clock."""
    algorithm = config.encoder.signature_algorithm
    ttl = config.token_ttl
    clock_skew = config.clock_skew
    allow_no_expiration = config.allow_no_expiration

    def jws_provider(loader: KeyLoaderInterface, clock: ClockInterface) -> JoserfcJwsProvider:
        return JoserfcJwsProvider(
            loader,
            algorithm,
            ttl,
            clock_skew,
            clock,
            allow_no_expiration=allow_no_expiration,
        )

    jws_provider.__annotations__ = {
        "loader": KeyLoaderInterface,
        "clock": ClockInterface,
        "return": JoserfcJwsProvider,
    }
    return jws_provider


def _encoder_factory() -> Callable[..., DefaultJwtEncoder]:
    """Return a factory building the default encoder over the JWS provider."""

    def default_encoder(provider: JwsProviderInterface) -> DefaultJwtEncoder:
        return DefaultJwtEncoder(provider)

    return default_encoder


def _encoder_service(config: JwtConfig) -> type[JwtEncoderInterface]:
    """Return the encoder service the manager reads, honouring an override.

    The override is validated as a ``JwtEncoderInterface`` class by
    ``EncoderConfig``, so it is returned as one.
    """
    override_service = config.encoder.service
    if override_service is None:
        return DefaultJwtEncoder
    return cast("type[JwtEncoderInterface]", override_service)


def _manager_factory(config: JwtConfig) -> Callable[..., JwtManager]:
    """Return a factory building the token manager over the encoder and enrichments.

    The enrichments are gathered from a ``Mapping`` keyed by the qualifiers the
    bundle's ``process`` hook aliased them under and passed as a definition
    argument the same hook fills, so an application adds one by registering it —
    never by reaching for the container, and with no empty-collection injection.
    """
    user_id_claim = config.user_id_claim
    issuer = config.issuer
    audience = tuple(config.audience)

    def jwt_manager(
        encoder: JwtEncoderInterface,
        dispatcher: EventDispatcherInterface,
        enrichments: Mapping[Hashable, PayloadEnrichmentInterface],
        enrichment_qualifiers: tuple[str, ...] = (),
    ) -> JwtManager:
        collected = [enrichments[qualifier] for qualifier in enrichment_qualifiers]
        enrichment = ChainEnrichment(collected) if collected else None
        return JwtManager(
            encoder,
            dispatcher,
            user_id_claim,
            enrichment,
            issuer=issuer,
            audience=audience,
        )

    jwt_manager.__annotations__ = {
        "encoder": JwtEncoderInterface,
        "dispatcher": EventDispatcherInterface,
        "enrichments": Mapping[Hashable, PayloadEnrichmentInterface],
        "enrichment_qualifiers": tuple[str, ...],
        "return": JwtManager,
    }
    return jwt_manager
