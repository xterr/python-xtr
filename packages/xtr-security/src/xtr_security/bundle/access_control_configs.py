"""One access-control rule as the application writes it.

A request pattern and the single attribute a matching request must hold, kept in
the bundle's config namespace so an application configures firewalls and access
rules from one import. The bundle turns each into a request matcher and the
attribute an :class:`~xtr_security_http.access_map.AccessMap` pairs it with.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_http.request_matcher.chain_request_matcher import ChainRequestMatcher
from xtr_security_http.request_matcher.host_request_matcher import HostRequestMatcher
from xtr_security_http.request_matcher.ip_request_matcher import IpRequestMatcher
from xtr_security_http.request_matcher.method_request_matcher import MethodRequestMatcher
from xtr_security_http.request_matcher.path_request_matcher import PathRequestMatcher

if TYPE_CHECKING:
    from xtr_security_http.request_matcher.request_matcher_interface import RequestMatcherInterface

__all__ = ["AccessControlConfig"]

_METHOD_TOKEN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")
"""An HTTP method is a token: no space, no separator, never empty."""


@dataclass(frozen=True, slots=True)
class AccessControlConfig:
    """A request pattern and the single attribute a matching request must hold.

    Rules are tried in order; the first whose ``path`` (and, when set, ``host``,
    ``methods`` and ``ips``) matches decides the request, by asking whether the
    token holds the one ``attribute``. One attribute per rule is deliberate — a
    rule that needs two conditions is two rules, or a single closure attribute.

    Attributes:
        path: A regular expression matched against the request path.
        attribute: The one attribute a matching request must satisfy —
            ``"ROLE_ADMIN"``, ``"IS_AUTHENTICATED"``, ``"PUBLIC_ACCESS"``, an
            ``OAUTH2_SCOPE(...)`` string.
        host: A regular expression matched against the request host, or ``None``.
        methods: The HTTP methods the rule applies to; every method when empty.
        ips: Client addresses the rule applies to; every address when empty.
        firewall: The firewall the rule belongs to, or ``None`` for any.

    Raises:
        InvalidArgumentError: When ``attribute`` is empty, ``path`` or ``host``
            is not a valid regular expression, a ``methods`` entry is not an
            HTTP method token, or an ``ips`` entry is neither an address nor a
            CIDR network.
    """

    path: str
    attribute: str
    host: str | None = None
    methods: tuple[str, ...] = ()
    ips: tuple[str, ...] = ()
    firewall: str | None = None

    def __post_init__(self) -> None:
        """Check the attribute, the two patterns, every method and every address.

        ``attribute`` must not be empty; ``path`` and ``host`` must compile as
        regular expressions; each ``methods`` entry must be an HTTP method token;
        each ``ips`` entry must parse as an address or CIDR network. Nothing is
        built here — :meth:`to_matcher` builds the matcher, and this check means
        a rule that cannot work is refused where the application wrote it rather
        than when the bundle assembles the access map.

        Raises:
            InvalidArgumentError: When ``attribute`` is empty, a pattern will not
                compile, a method is not a token, or an address entry is neither
                an address nor a network.
        """
        if not self.attribute:
            raise InvalidArgumentError("An access-control rule needs an attribute to require.")
        for label, regex in (("path", self.path), ("host", self.host)):
            if regex is not None:
                try:
                    _ = re.compile(regex)
                except re.error as error:
                    raise InvalidArgumentError(
                        f"The access-control {label} {regex!r} is not a valid regular "
                        f"expression: {error}.",
                    ) from error
        for method in self.methods:
            if _METHOD_TOKEN.fullmatch(method) is None:
                raise InvalidArgumentError(
                    f"The access-control method {method!r} is not an HTTP method token.",
                )
        for entry in self.ips:
            try:
                _ = ipaddress.ip_network(entry, strict=False)
            except ValueError as error:
                raise InvalidArgumentError(
                    f"The access-control address {entry!r} is not a valid address or network.",
                ) from error

    def to_matcher(self) -> RequestMatcherInterface:
        """Return the request matcher this configuration describes.

        Raises:
            InvalidArgumentError: When ``path`` or ``host`` is not a valid
                regular expression.
        """
        matchers: list[RequestMatcherInterface] = [PathRequestMatcher(self.path)]
        if self.host is not None:
            matchers.append(HostRequestMatcher(self.host))
        if self.methods:
            matchers.append(MethodRequestMatcher(self.methods))
        if self.ips:
            matchers.append(IpRequestMatcher(self.ips))
        return ChainRequestMatcher(matchers)
