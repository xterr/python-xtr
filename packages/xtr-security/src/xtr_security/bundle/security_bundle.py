"""The xtr-security bundle: the family's one integration with the container.

Reads a :class:`SecurityConfig` and puts the whole security machine under the
container — the token storage and authorization checker scoped to a request, the
voters and the decision manager, the user providers and password hashers, and,
per firewall, its own event dispatcher, authenticators, access map, entry
point and exception listener, gathered into a :class:`FirewallMap`. The
exception listener — one per firewall, built from that firewall's parts —
turns a security error into a response on the http-kernel lifecycle, and the
firewall — a subscriber over the same lifecycle's events — runs the chain of
the firewall that matched each request, before routing.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    PassStage,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_dependency_injection.kernel.kernel import BUNDLE_PASS_PRIORITY
from xtr_event_dispatcher.bundle import EventDispatcherBundle
from xtr_http_kernel.bundle import HttpKernelBundle
from xtr_security_core import (
    AccessDecisionManager,
    AccessDecisionStrategyInterface,
    VoterInterface,
)

from xtr_security.access_token import OidcTokenHandlerFactory
from xtr_security.bundle._core_services_wiring import register_core_security_services
from xtr_security.bundle.oidc_configs import OidcLoginConfig
from xtr_security.bundle.security_config import SecurityConfig

from ._wiring import VOTER_TAG, build_firewall_map
from .make_firewalls_event_dispatcher_traceable_pass import (
    MakeFirewallsEventDispatcherTraceablePass,
)
from .make_firewalls_manager_listener_traceable_pass import (
    MakeFirewallsManagerListenerTraceablePass,
)
from .refuse_stateful_firewalls_without_session_storage_pass import (
    RefuseStatefulFirewallsWithoutSessionStoragePass,
)
from .register_global_security_event_listeners_pass import RegisterGlobalSecurityEventListenersPass
from .register_per_call_listeners_pass import RegisterPerCallListenersPass
from .sort_firewall_listeners_pass import SortFirewallListenersPass

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceConfigurator

    from xtr_security.access_token.oidc_token_handler_factory import (
        _AsyncCloseable,  # pyright: ignore[reportPrivateUsage] -- the family's own close contract
    )

__all__ = ["SecurityBundle"]

_TRACEABLE_PASS_PRIORITY = 10
"""Ahead of the bundles' own passes, once autoconfiguration has run; decorations resolve later."""


@final
@required_bundle(EventDispatcherBundle)
@required_bundle(HttpKernelBundle)
@required_bundle("xtr_clock.bundle:ClockBundle", ignore_on_invalid=True)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("security", config=SecurityConfig)
class SecurityBundle(Bundle[SecurityConfig]):
    """Configures the xtr security family from one :class:`SecurityConfig`."""

    def __init__(self) -> None:
        """Start with the strategy the configuration has not changed yet."""
        self._strategy: AccessDecisionStrategyInterface = (
            SecurityConfig().access_decision_manager.build()
        )
        self._trace_votes = False
        self._user_classes: tuple[str, ...] = ()
        self._oidc_closeables: list[_AsyncCloseable] = []

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Autoconfigure every application voter, and register the firewall dispatchers' passes.

        The firewalls' dispatchers and manager listeners are traced before the
        decorations resolve, and take the main dispatcher's security listeners
        once the event dispatcher bundle's ``RegisterListenersPass`` has worked
        both out. The firewalls' listener chains are ordered after every
        bundle's ``process`` hook, so a listener another bundle adds to one is
        sorted with the rest.

        The firewall itself runs as one listener per lifecycle event, loaded
        here so the scan finds it whatever the application configures.
        """
        _ = builder.register_for_autoconfiguration(VoterInterface).add_tag(VOTER_TAG)
        builder.add_compiler_pass(
            MakeFirewallsEventDispatcherTraceablePass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=_TRACEABLE_PASS_PRIORITY,
        )
        builder.add_compiler_pass(
            MakeFirewallsManagerListenerTraceablePass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=_TRACEABLE_PASS_PRIORITY,
        )
        builder.add_compiler_pass(
            RegisterGlobalSecurityEventListenersPass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=BUNDLE_PASS_PRIORITY - 1,
        )
        # Between the container's remove-if-missing pass (priority 100) and
        # the chain sorting below, so the refusal is heard first.
        builder.add_compiler_pass(
            RefuseStatefulFirewallsWithoutSessionStoragePass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=0,
        )
        builder.add_compiler_pass(
            SortFirewallListenersPass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=BUNDLE_PASS_PRIORITY - 1,
        )
        # Behind the listener maps' own passes: the per-call listeners join
        # the map every other listener has been placed in, at the positions
        # they run in.
        builder.add_compiler_pass(
            RegisterPerCallListenersPass(),
            stage=PassStage.BEFORE_OPTIMIZATION,
            priority=BUNDLE_PASS_PRIORITY - 2,
        )

    @override
    def load_extension(
        self,
        config: SecurityConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the security services from ``config``."""
        self._trace_votes = (
            config.trace_votes
            if config.trace_votes is not None
            else bool(builder.get_parameter("kernel.debug"))
        )
        self._strategy = config.access_decision_manager.build()

        register_core_security_services(
            services,
            builder,
            config,
            strategy=self._strategy,
            trace_votes=self._trace_votes,
        )

        build_firewall_map(
            services,
            self._bind_oidc_closeables(config),
            clock_active=bundle_active(builder, "clock"),
            logging_active=bundle_active(builder, "logging"),
        )

        # The firewall runs the chain of the firewall each request matched,
        # over the lifecycle's own events; the listeners resolve the map per
        # call, from the request's scope.
        services.load("xtr_security.event_listener.firewall_listener")

        if bundle_active(builder, "console"):
            self._user_classes = tuple(
                key if isinstance(key, str) else f"{key.__module__}:{key.__qualname__}"
                for key in config.password_hashers
            )
            if _has_oidc_token_generators(config):
                services.load("xtr_security_http.command.oidc_token_generate_command")
            # A scan finds what a module defines, not what it imports: the hasher
            # command is scanned where it is defined.
            services.load(
                "xtr_security.command",
                "xtr_password_hasher.command.user_password_hash_command",
            )

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Collect every tagged voter and build the decision manager over them.

        Runs after every bundle loaded, so the builder holds every voter — the
        built-ins and every application voter the autoconfiguration tagged. Each
        is aliased to
        :class:`~xtr_security_core.authorization.voter.voter_interface.VoterInterface`
        under a qualifier of its own, so the manager gathers them from a
        ``Mapping`` and orders them as collected; the bundle wraps each in a
        :class:`~xtr_security_core.TraceableVoter` when tracing is on.

        With a console, ``security:hash-password`` is handed the configured
        user classes, the first of which it hashes for by default.
        """
        voter_keys = tuple(builder.find_tagged_service_ids(VOTER_TAG))
        qualifiers = tuple(f"security_voter_{index}" for index in range(len(voter_keys)))
        for qualifier, key in zip(qualifiers, voter_keys, strict=True):
            builder.set_alias(
                VoterInterface,
                key[0],
                alias_qualifier=qualifier,
                target_qualifier=key[1],
            )
        _ = builder.get_definition(AccessDecisionManager).set_argument(
            "voter_qualifiers", qualifiers
        )
        if bundle_active(builder, "console"):
            from xtr_security.command import (  # noqa: PLC0415 -- only with xtr-console installed
                UserPasswordHashCommand,
            )

            _ = builder.get_definition(UserPasswordHashCommand).set_argument(
                "user_classes", self._user_classes
            )

    @override
    async def shutdown(self) -> None:
        """Close every discovery key-set provider's HTTP client built this run.

        An OIDC firewall's discovery provider lazily opens an HTTP client; those
        that opened one are collected here so the client does not outlive the
        kernel. The sink is emptied in place: the OIDC factories the extension
        bound hold this very list, so a run after this one records into the same
        sink and is closed by the next shutdown.

        Every provider is closed even when one fails, so one leaking client
        cannot keep the others open; the sink is cleared whatever happens, and
        the failures are re-raised together as an :class:`ExceptionGroup`.

        Raises:
            ExceptionGroup: When one or more providers raised while closing.
        """
        failures: list[Exception] = []
        for closeable in self._oidc_closeables:
            try:
                await closeable.aclose()
            except Exception as error:  # noqa: BLE001 -- gather every failure, re-raised below
                failures.append(error)
        self._oidc_closeables.clear()
        if failures:
            raise ExceptionGroup("OIDC key-set providers failed to close", failures)

    def _bind_oidc_closeables(self, config: SecurityConfig) -> SecurityConfig:
        """Return ``config`` with every OIDC factory recording into this bundle's sink.

        A config with no OIDC factory is returned untouched, so the zero-config
        path builds nothing new.
        """
        if not any(
            isinstance(factory, OidcTokenHandlerFactory)
            for factory in config.token_handler_factories
        ):
            return config
        return replace(
            config,
            token_handler_factories=tuple(
                factory.with_closeables(self._oidc_closeables)
                if isinstance(factory, OidcTokenHandlerFactory)
                else factory
                for factory in config.token_handler_factories
            ),
        )


def _has_oidc_token_generators(config: SecurityConfig) -> bool:
    """Tell whether any firewall mints OIDC tokens through the command."""
    return any(
        isinstance(authenticator, OidcLoginConfig) and authenticator.token_generator is not None
        for firewall in config.firewalls.values()
        for authenticator in firewall.authenticators
    )
