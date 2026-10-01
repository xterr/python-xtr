"""One firewall as the application writes it.

A firewall claims a slice of the request space — by path, host, methods, or a
matcher of its own — and decides how requests to it authenticate. The bundle
turns each into the runtime pieces a :class:`FirewallContext` groups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xtr_security_http.request_matcher.callable_request_matcher import CallableRequestMatcher
from xtr_security_http.request_matcher.chain_request_matcher import ChainRequestMatcher
from xtr_security_http.request_matcher.host_request_matcher import HostRequestMatcher
from xtr_security_http.request_matcher.method_request_matcher import MethodRequestMatcher
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

from xtr_security.exception import InvalidConfigurationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.requests import Request
    from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface

__all__ = ["FirewallConfig"]


@dataclass(frozen=True, slots=True)
class FirewallConfig:
    """How a firewall claims requests, and how it authenticates them.

    Attributes:
        pattern: A regular expression matched against the request path, or
            ``None`` to leave the claim to the other matchers.
        host: A regular expression matched against the request host.
        methods: The HTTP methods the firewall claims; every method when empty.
        request_matcher: A callable deciding the claim, tried last.
        security: Whether the firewall authenticates at all; ``False`` lets every
            request it claims through untouched.
        stateless: Whether the firewall keeps no session — only ``True`` is
            accepted in this version.
        provider: The name of the user provider the firewall loads users from,
            or ``None`` to leave it to the authenticator.
        user_checker: A user-checker service type run around authentication, or
            ``None`` for the default in-memory checker.
        entry_point: The name of the authenticator whose challenge answers an
            unauthenticated request, or ``None`` to resolve it automatically.
        access_denied_handler: A handler service type answering a denied,
            fully-authenticated caller, or ``None`` for a plain refusal.
        authenticators: The authenticator configurations the firewall runs, each
            an instance a registered factory's ``config_type`` matches.
        required_badges: Badge types every passport must carry to authenticate.

    Raises:
        InvalidConfigurationError: When ``stateless`` is ``False``, or a secured
            firewall names no authenticators.
    """

    pattern: str | None = None
    host: str | None = None
    methods: tuple[str, ...] = ()
    request_matcher: Callable[[Request], bool] | None = None
    security: bool = True
    stateless: bool = True
    provider: str | None = None
    user_checker: type | None = None
    entry_point: str | None = None
    access_denied_handler: type | None = None
    authenticators: tuple[object, ...] = ()
    required_badges: tuple[type, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Refuse a stateful firewall, and a secured one with no authenticators."""
        if not self.stateless:
            raise InvalidConfigurationError(
                "Only stateless firewalls are supported; set stateless=True.",
            )
        if self.security and not self.authenticators:
            raise InvalidConfigurationError(
                "A secured firewall needs at least one authenticator; "
                "set security=False for an open firewall.",
            )
        _ = self.to_matcher()

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
