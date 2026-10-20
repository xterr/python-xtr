"""The logout machinery a firewall with a logout path wires.

The logout itself is a chain step parked on the firewall context's own
logout slot — not the listener chain, not the sorting pass: the firewall
inserts it where its ``-127`` priority runs. What the logout announces is
answered on the firewall's own dispatcher, where each listener this
configuration turns on does its part, and one generator per application
hands every firewall's logout address to whatever renders a page. The
generator is told which firewall the request runs under — the matched
firewall, named per request — so a keyless generation resolves on the
requests no token answers for too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from xtr_dependency_injection import Injected, Target, named_factory
from xtr_event_dispatcher.bundle import SUBSCRIBER_TAG
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_kernel import RequestEvent
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_security_core import TokenStorageInterface
from xtr_security_csrf.csrf_token_manager_interface import (
    CsrfTokenManagerInterface,
)
from xtr_security_http import HttpUtils
from xtr_security_http._security_state import security_state_of

from xtr_security.bundle.firewall_dispatcher_name import firewall_dispatcher_name
from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_dependency_injection import ServiceConfigurator
    from xtr_security_http import ClearedCookie

    from xtr_security.firewall_config import FirewallConfig
    from xtr_security.logout_config import LogoutConfig

__all__ = [
    "logout_context_key",
    "logout_listener_name",
    "name_the_current_firewall",
    "register_logout",
    "register_logout_url_generator",
]


def logout_context_key(name: str, firewall: FirewallConfig) -> str:
    """Return the context a firewall's logout is registered under.

    The firewall's own context key when it names one, else its name — the
    same value the generator's registration carries, so the per-request
    naming and the registration it resolves against cannot disagree.
    """
    return firewall.context_key if firewall.context_key is not None else name


def logout_listener_name(firewall_name: str) -> str:
    """The qualifier of a firewall's logout chain step."""
    return f"{firewall_name}#logout_listener"


def register_logout(
    services: ServiceConfigurator,
    name: str,
    firewall: FirewallConfig,
    logout: LogoutConfig,
) -> str:
    """Register the logout step and the listeners that answer its event.

    The step is registered as a service of its own and handed to the
    firewall's context, which parks it on its logout slot — the firewall
    runs it where its priority sits, behind the steps that authenticate and
    decide. The event it announces is answered on the firewall's own
    dispatcher by the listeners the configuration turns on: the default
    redirect every logout ends in, the site-data header, the cookie
    clearing, the session invalidation.

    Raises:
            InvalidConfigurationError: When the configuration asks for a
                cross-site request forgery check on a stateless firewall,
                which has no session to store the tokens in.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        LogoutListener,
    )

    if (logout.enable_csrf or logout.clear_csrf_tokens) and firewall.stateless:
        raise InvalidConfigurationError(
            f'The logout of the firewall "{name}" asks for a cross-site request '
            "forgery check, which needs the session its tokens are stored in; "
            "set stateless=False.",
        )

    def logout_listener(
        storage: TokenStorageInterface,
        http_utils: HttpUtils,
        dispatcher: EventDispatcherInterface,
        bridge: StarletteHttpFactoryInterface,
        csrf_token_manager: object | None = None,
    ) -> LogoutListener:
        """Build the step over one firewall's logout parts."""
        return LogoutListener(
            storage,
            http_utils,
            dispatcher,
            bridge,
            cast("CsrfTokenManagerInterface | None", csrf_token_manager),
            csrf_parameter=logout.csrf_parameter,
            csrf_token_id=logout.csrf_token_id,
            logout_path=logout.path,
        )

    annotations: dict[str, object] = {
        "storage": TokenStorageInterface,
        "http_utils": HttpUtils,
        "dispatcher": Annotated[EventDispatcherInterface, Target(firewall_dispatcher_name(name))],
        "bridge": StarletteHttpFactoryInterface,
        "return": LogoutListener,
    }
    if logout.enable_csrf:
        annotations["csrf_token_manager"] = CsrfTokenManagerInterface
    logout_listener.__annotations__ = annotations
    logout_listener.__name__ = f"logout_listener_{name}"
    logout_listener.__qualname__ = logout_listener.__name__
    _ = services.set(logout_listener, qualifier=logout_listener_name(name), lifetime="scoped")

    dispatcher = firewall_dispatcher_name(name)
    _register_subscriber(
        services,
        dispatcher,
        f"default_logout_listener_{name}",
        _default_logout_listener(logout.target_path),
    )
    if logout.clear_site_data is not None:
        _register_subscriber(
            services,
            dispatcher,
            f"clear_site_data_listener_{name}",
            _clear_site_data_listener(logout.clear_site_data),
        )
    if logout.cookie_clearing:
        _register_subscriber(
            services,
            dispatcher,
            f"cookie_clearing_listener_{name}",
            _cookie_clearing_listener(logout.cookie_clearing),
        )
    if logout.invalidate_session and not firewall.stateless:
        _register_subscriber(
            services,
            dispatcher,
            f"session_logout_listener_{name}",
            _session_logout_listener(),
        )
    return logout_listener_name(name)


def register_logout_url_generator(
    services: ServiceConfigurator,
    registrations: Mapping[str, tuple[str, str | None]],
) -> None:
    """Register the one generator, every firewall's logout registered on it.

    Each firewall with a logout registers its path and its context — the
    shared context of a firewall pair, a stateless API beside a stateful
    login — so a keyless generation resolves over the token, the current
    firewall or that context, in the generator's own order. The generator
    is scoped like the token storage it reads: the current firewall a
    keyless generation resolves over is the request's own, and what one
    request named does not answer for the next.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        LogoutUrlGenerator,
    )

    def logout_url_generator(token_storage: TokenStorageInterface) -> LogoutUrlGenerator:
        """Build the generator with every firewall's logout registered on it."""
        generator = LogoutUrlGenerator(token_storage=token_storage)
        for firewall_name, (path, context) in registrations.items():
            generator.register_listener(firewall_name, path, None, None, None, context)
        return generator

    logout_url_generator.__annotations__ = {
        "token_storage": TokenStorageInterface,
        "return": LogoutUrlGenerator,
    }
    _ = services.set(logout_url_generator, lifetime="scoped")


def name_the_current_firewall(
    contexts: Mapping[str, str],
) -> Callable[..., Awaitable[None]]:
    """Return the request listener naming the matched firewall on the generator.

    The generator is a service of the request — scoped, so what one request
    named never answers for the next; no reset is wired, the scope is the
    reset. The listener runs after the firewall matched the request and
    parked its context, and names that firewall — with the context its
    logout was registered under — so a keyless generation resolves on the
    requests no token answers for: an anonymous page under a firewall with
    a logout, rendering that logout's address.

    Args:
        contexts: Each firewall with a logout, mapped to the context its
            logout was registered under.
    """
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        LogoutUrlGenerator,
    )

    async def name_the_matched_firewall(
        event: RequestEvent, generator: Injected[LogoutUrlGenerator]
    ) -> None:
        context = security_state_of(event.state).firewall_context
        if context is None:
            return
        generator.set_current_firewall(context.name, contexts.get(context.name))

    name_the_matched_firewall.__annotations__ = {
        "event": RequestEvent,
        "generator": Injected[LogoutUrlGenerator],
        "return": None,
    }
    return name_the_matched_firewall


def _register_subscriber(
    services: ServiceConfigurator,
    dispatcher: str,
    listener_name: str,
    factory: Callable[..., object],
) -> None:
    """Register one logout event listener on the firewall's own dispatcher."""
    _ = services.set(
        named_factory(factory, listener_name),
        qualifier=dispatcher,
    ).add_tag(SUBSCRIBER_TAG, dispatcher=dispatcher)


def _default_logout_listener(target_path: str) -> Callable[..., object]:
    """Return the factory of the redirect every unanswered logout ends in."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        DefaultLogoutListener,
    )

    def default_logout_listener(http_utils: HttpUtils) -> DefaultLogoutListener:
        return DefaultLogoutListener(http_utils, target_path)

    default_logout_listener.__annotations__ = {
        "http_utils": HttpUtils,
        "return": DefaultLogoutListener,
    }
    return default_logout_listener


def _clear_site_data_listener(site_data: Sequence[str]) -> Callable[..., object]:
    """Return the factory of the header dropping the browser's site data."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        ClearSiteDataListener,
    )

    def clear_site_data_listener() -> ClearSiteDataListener:
        return ClearSiteDataListener(site_data)

    clear_site_data_listener.__annotations__ = {"return": ClearSiteDataListener}
    return clear_site_data_listener


def _cookie_clearing_listener(cookies: Mapping[str, ClearedCookie]) -> Callable[..., object]:
    """Return the factory of the headers clearing the configured cookies."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        CookieClearingListener,
    )

    def cookie_clearing_listener() -> CookieClearingListener:
        return CookieClearingListener(cookies)

    cookie_clearing_listener.__annotations__ = {"return": CookieClearingListener}
    return cookie_clearing_listener


def _session_logout_listener() -> Callable[..., object]:
    """Return the factory of the invalidation ending the session's login."""
    from xtr_security_http import (  # noqa: PLC0415 -- the family's logout import
        SessionLogoutListener,
    )

    def session_logout_listener() -> SessionLogoutListener:
        return SessionLogoutListener()

    session_logout_listener.__annotations__ = {"return": SessionLogoutListener}
    return session_logout_listener
