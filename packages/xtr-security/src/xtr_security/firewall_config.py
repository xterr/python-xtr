"""One firewall as the application writes it.

A firewall claims a slice of the request space — by path, host, methods, or a
matcher of its own — and decides how requests to it authenticate. The bundle
turns each into the runtime pieces a :class:`FirewallContext` groups.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xtr_http_foundation import (
    CallableRequestMatcher,
    ChainRequestMatcher,
    HostRequestMatcher,
    MethodRequestMatcher,
    PathRequestMatcher,
)
from xtr_security_core.exception import InvalidArgumentError

from xtr_security.exception import InvalidConfigurationError
from xtr_security.login_throttling_config import (  # noqa: TC001 -- a field type the kernel reads at runtime
    LoginThrottlingConfig,
)
from xtr_security.logout_config import (  # noqa: TC001 -- a field type the kernel reads at runtime
    LogoutConfig,
)
from xtr_security.switch_user_config import (  # noqa: TC001 -- a field type the kernel reads at runtime
    SwitchUserConfig,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["FirewallConfig"]

_KNOWN_SESSION_STRATEGIES = frozenset(("none", "migrate", "invalidate"))


@dataclass(frozen=True, slots=True)
class FirewallConfig:
    """How a firewall claims requests, and how it authenticates them.

    Attributes:
        pattern: A regular expression matched against the request path, or
            ``None`` to leave the claim to the other matchers.
        host: A regular expression matched against the request host.
        methods: The HTTP methods the firewall claims; every method when empty.
        request_matcher: A callable deciding the claim against the request
            message, tried last.
        security: Whether the firewall authenticates at all; ``False`` lets every
            request it claims through untouched.
        stateless: Whether the firewall keeps no session. A stateful firewall
            (``stateless=False``) restores the token its session carries on
            every request, through the session storage the application
            registered as a ``SessionStorageInterface`` service.
        context_key: The name the firewall's security context is stored under
            in the session — the part after the ``_security.`` prefix — or
            ``None`` for the firewall's own name. Two firewalls sharing one
            session keep their contexts apart by it.
        session_strategy: What a successful login does to the session it
            reattached — ``migrate`` (the default) rotates its ID keeping its
            attributes, ``invalidate`` empties it, ``none`` leaves it alone.
            Meaningful on a stateful firewall only.
        provider: The name of the user provider the firewall loads users from,
            or ``None`` to leave it to the authenticator.
        user_checker: A user-checker service type run around authentication, or
            ``None`` for the default in-memory checker.
        entry_point: The name of the authenticator whose challenge answers an
            unauthenticated request, or ``None`` to resolve it automatically.
        access_denied_handler: A handler service type answering a denied,
            fully-authenticated caller, or ``None`` for a plain refusal.
        scope_denied_handler: A handler service type answering a caller whose
            token lacks a scope an access rule asks for — wrapped by the
            bundle's ``WWW-Authenticate`` answer — or ``None`` for that answer
            alone.
        authenticators: The authenticator configurations the firewall runs, each
            an instance a registered factory's ``config_type`` matches.
        required_badges: Badge types every passport must carry to authenticate.
        csrf_route_markers: Whether the routes this firewall claims prove
            themselves with ``IsCsrfTokenValid`` markers — wiring the
            forgery-token manager for them even when no login or logout of
            the firewall asks for a token. The tokens travel in the session
            the request reattached, so a stateless firewall declaring them
            fails the build.
        logout: The logout the firewall's requests can ask for, or ``None``
            when the firewall has none.
        switch_user: The switch-user block the firewall's callers switch
            by, or ``None`` when the firewall has none.
        login_throttling: How the firewall's logins are counted and
            refused, or ``None`` to let every attempt through uncounted.
        re_authentication_entry_point: A service type implementing
            :class:`~xtr_security_http.entry_point.re_authentication_entry_point_interface.ReAuthenticationEntryPointInterface`,
            starting a fresh proof for a caller who is already
            authenticated — or ``None`` for a plain ``403`` refusal.
        listeners: The qualifiers of the firewall's listener chain, each naming
            a listener aliased under
            :class:`~xtr_security_http.firewall.firewall_listener_interface.FirewallListenerInterface`.
            The bundle parks them on the firewall's context definition, where
            its sorting pass orders them — by priority, highest first — so the
            chain the context carries runs in that order.

    Raises:
        InvalidConfigurationError: When a secured firewall names no
            authenticators, or the session strategy is unknown.
        InvalidArgumentError: When ``pattern`` or ``host`` is not a valid
            regular expression, or ``context_key`` is empty.
    """

    pattern: str | None = None
    host: str | None = None
    methods: tuple[str, ...] = ()
    request_matcher: Callable[[ServerRequestInterface], bool] | None = None
    security: bool = True
    stateless: bool = True
    context_key: str | None = None
    session_strategy: str = "migrate"
    provider: str | None = None
    user_checker: type | None = None
    entry_point: str | None = None
    access_denied_handler: type | None = None
    scope_denied_handler: type | None = None
    authenticators: tuple[object, ...] = ()
    required_badges: tuple[type, ...] = field(default_factory=tuple)
    csrf_route_markers: bool = False
    logout: LogoutConfig | None = None
    switch_user: SwitchUserConfig | None = None
    login_throttling: LoginThrottlingConfig | None = None
    re_authentication_entry_point: type | None = None
    listeners: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Refuse a secured firewall with no authenticators, a bad regex or strategy.

        Raises:
            InvalidConfigurationError: When a secured firewall names no
                authenticators, or the session strategy is unknown.
            InvalidArgumentError: When ``pattern`` or ``host`` is not a valid
                regular expression, or ``context_key`` is empty.
        """
        if self.context_key == "":
            raise InvalidArgumentError(
                "The firewall context key must not be empty; two firewalls sharing "
                "one session would read each other's contexts.",
            )
        if self.session_strategy not in _KNOWN_SESSION_STRATEGIES:
            raise InvalidConfigurationError(
                f"Unknown session strategy {self.session_strategy!r}; "
                f"known are {sorted(_KNOWN_SESSION_STRATEGIES)}.",
            )
        if self.security and not self.authenticators:
            raise InvalidConfigurationError(
                "A secured firewall needs at least one authenticator; "
                "set security=False for an open firewall.",
            )
        for label, regex in (("pattern", self.pattern), ("host", self.host)):
            if regex is not None:
                try:
                    _ = re.compile(regex)
                except re.error as error:
                    raise InvalidArgumentError(
                        f"The firewall {label} {regex!r} is not a valid regular expression: "
                        f"{error}.",
                    ) from error

    def to_matcher(self) -> RequestMatcherInterface:
        """Return the request matcher this firewall claims requests with.

        Composes a path, host, method and callable matcher into a chain; a
        firewall with no constraints becomes a chain of none, which claims every
        request — the catch-all a last-registered firewall relies on.

        Raises:
            InvalidArgumentError: When ``pattern`` or ``host`` is not a valid
                regular expression.
        """
        matchers: list[RequestMatcherInterface] = []
        if self.pattern is not None:
            matchers.append(PathRequestMatcher(self.pattern))
        if self.host is not None:
            matchers.append(HostRequestMatcher(self.host))
        if self.methods:
            matchers.append(MethodRequestMatcher(self.methods))
        if self.request_matcher is not None:
            matchers.append(CallableRequestMatcher(self.request_matcher))
        return ChainRequestMatcher(matchers)
