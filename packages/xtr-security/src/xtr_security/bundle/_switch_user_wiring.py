"""The switch-user step a firewall's callers switch by, and its generator.

The switch itself is a chain step — parked beside the manager's own, and
ordered after it by the sorting pass through the class's
``@FirewallListenerOrder`` declaration — because a switch begins from the
token the request already holds, which only the manager's pass can have
set. The addresses a page switches by come from the one generator, which
answers the switch-user configuration of the firewall the request runs in
through a lookup built from the firewall map.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_security_core import (
    AccessDecisionManagerInterface,
    TokenStorageInterface,
)
from xtr_security_core.user.user_provider_interface import (
    UserProviderInterface,
)
from xtr_security_csrf.csrf_token_manager_interface import (
    CsrfTokenManagerInterface,
)
from xtr_security_http import (
    HttpUtils,
    ImpersonateUrlGenerator,
    SwitchUserListener,
)
from xtr_security_http._security_state import security_state_of
from xtr_security_http.impersonate.switch_user_config import SwitchUserConfig
from xtr_security_http.impersonate.switch_user_config_lookup_interface import (
    SwitchUserConfigLookupInterface,
)
from xtr_security_http.security_request_attributes import (
    SecurityRequestAttributes,
)

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.user.user_checker_interface import UserCheckerInterface

    from xtr_security.firewall_config import FirewallConfig
    from xtr_security.switch_user_config import SwitchUserConfig as FirewallSwitchUserConfig

__all__ = [
    "register_switch_user",
    "switch_user_listener_name",
]


def switch_user_listener_name(firewall_name: str) -> str:
    """The qualifier of a firewall's switch-user chain step."""
    return f"{firewall_name}#switch_user_listener"


def register_switch_user(  # noqa: PLR0913 -- one step built from its firewall's parts
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    settings: FirewallSwitchUserConfig,
    provider_qualifier: str | None,
    *,
    csrf_wired: bool,
) -> str:
    """Register the switch step on the firewall's chain, and return its qualifier.

    The step is aliased under the firewall listener interface and parked on
    the chain beside the manager's own step; the sorting pass orders it
    after the manager through the class's own
    ``@FirewallListenerOrder`` declaration, so a switch begins from the
    token the request already holds. The step is handed the firewall's own
    dispatcher, so the switch event it announces is heard where the
    firewall's other events are. A switch that asks for a forgery
    token needs the session its tokens are stored in: a stateless firewall
    asking for one is refused, here, naming the firewall.

    Raises:
        InvalidConfigurationError: When the switch asks for a cross-site
            request forgery check on a stateless firewall, which has no
            session to store the tokens in.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's switch import
        FirewallListenerInterface,
    )

    if settings.enable_csrf and firewall.stateless:
        raise InvalidConfigurationError(
            f'The switch-user of the firewall "{name}" asks for a cross-site request '
            "forgery check, which needs the session its tokens are stored in; "
            "set stateless=False.",
        )

    qualifier = switch_user_listener_name(name)

    def switch_user_listener(  # noqa: PLR0913, PLR0917 -- the listener's own wiring shape
        token_storage: TokenStorageInterface,
        provider: UserProviderInterface,
        decision_manager: AccessDecisionManagerInterface,
        bridge: StarletteHttpFactoryInterface,
        http_utils: HttpUtils,
        dispatcher: EventDispatcherInterface,
        user_checker: UserCheckerInterface | None = None,
        csrf_token_manager: CsrfTokenManagerInterface | None = None,
    ) -> SwitchUserListener:
        """Build the step over one firewall's switch parts."""
        from xtr_security_core import InMemoryUserChecker  # noqa: PLC0415 -- default checker

        return SwitchUserListener(
            token_storage,
            provider,
            cast("UserCheckerInterface", user_checker or InMemoryUserChecker()),
            name,
            decision_manager,
            bridge,
            http_utils,
            username_parameter=settings.parameter,
            role=settings.role,
            dispatcher=dispatcher,
            stateless=firewall.stateless,
            path=settings.path,
            csrf_token_manager=csrf_token_manager,
            csrf_parameter=settings.csrf_parameter,
            csrf_token_id=settings.csrf_token_id,
        )

    annotations: dict[str, object] = {
        "token_storage": TokenStorageInterface,
        "provider": (
            Annotated[UserProviderInterface, Target(provider_qualifier)]
            if provider_qualifier is not None
            else UserProviderInterface
        ),
        "decision_manager": AccessDecisionManagerInterface,
        "bridge": StarletteHttpFactoryInterface,
        "http_utils": HttpUtils,
        "dispatcher": Annotated[EventDispatcherInterface, Target(firewall_dispatcher_name(name))],
        "return": SwitchUserListener,
    }
    if firewall.user_checker is not None:
        annotations["user_checker"] = firewall.user_checker
    if settings.enable_csrf and csrf_wired:
        annotations["csrf_token_manager"] = CsrfTokenManagerInterface
    switch_user_listener.__annotations__ = annotations
    switch_user_listener.__name__ = f"switch_user_listener_{name}"
    switch_user_listener.__qualname__ = switch_user_listener.__name__
    _ = services.set(switch_user_listener, qualifier=qualifier, lifetime="scoped")
    services.alias(
        FirewallListenerInterface,
        SwitchUserListener,
        alias_qualifier=qualifier,
        target_qualifier=qualifier,
    )
    return qualifier


@final
class _FirewallConfigLookup(SwitchUserConfigLookupInterface):
    """Answers the switch-user configuration of the firewall a request runs in.

    Built from the firewall map the bundle itself reads: the request's
    security state names the firewall that matched it, and the lookup
    answers that firewall's block — or ``None`` for a request no firewall
    with a switch has claimed.
    """

    __slots__ = ("_configs",)

    def __init__(self, configs: Mapping[str, FirewallSwitchUserConfig]) -> None:
        """Record each firewall's switch-user block, keyed by its name."""
        self._configs = dict(configs)

    @override
    async def get_switch_user_config(
        self,
        request: ServerRequestInterface,
    ) -> SwitchUserConfig | None:
        """Return the switch-user block of the request's firewall, or ``None``."""
        bag = request.get_attribute(SecurityRequestAttributes.STATE_BAG)
        if bag is None:
            return None
        context = security_state_of(cast("MutableMapping[str, object]", bag)).firewall_context
        if context is None:
            return None
        settings = self._configs.get(context.name)
        if settings is None:
            return None
        return SwitchUserConfig(
            parameter=settings.parameter,
            enable_csrf=settings.enable_csrf,
            csrf_parameter=settings.csrf_parameter,
            csrf_token_id=settings.csrf_token_id,
            path=settings.path,
        )


def register_impersonate_url_generator(
    services: ServiceConfigurator,
    registrations: Mapping[str, FirewallSwitchUserConfig],
    *,
    csrf_wired: bool,
) -> None:
    """Register the one generator every firewall's switch addresses come from.

    Scoped like the token storage it reads: whether the current user is
    impersonating anyone is the current request's own question, and what
    one request's generator answered never answers for the next. The
    lookup it answers its configuration through is built from the firewall
    map, so the generator knows nothing of the bundle behind it.
    """
    lookup = _FirewallConfigLookup(registrations)

    def impersonate_url_generator(
        token_storage: TokenStorageInterface,
        csrf_token_manager: CsrfTokenManagerInterface | None = None,
    ) -> ImpersonateUrlGenerator:
        """Build the generator over the lookup and the request's storage."""
        return ImpersonateUrlGenerator(
            lookup,
            token_storage,
            csrf_token_manager=csrf_token_manager,
        )

    annotations: dict[str, object] = {
        "token_storage": TokenStorageInterface,
        "return": ImpersonateUrlGenerator,
    }
    if csrf_wired and any(settings.enable_csrf for settings in registrations.values()):
        annotations["csrf_token_manager"] = CsrfTokenManagerInterface
    impersonate_url_generator.__annotations__ = annotations
    impersonate_url_generator.__name__ = "impersonate_url_generator"
    impersonate_url_generator.__qualname__ = impersonate_url_generator.__name__
    _ = services.set(impersonate_url_generator, lifetime="scoped")
