"""The firewalls of an application: found by name, or by matching a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .exception.unknown_firewall_error import UnknownFirewallError
from .firewall_map_interface import FirewallMapInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_http_foundation import RequestMatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

    from xtr_security_http.firewall.exception_listener import ExceptionListener
    from xtr_security_http.firewall.firewall_listener_interface import (
        FirewallListenerInterface,
    )

    from .firewall_context_interface import FirewallContextInterface

__all__ = ["FirewallMap"]


@final
class FirewallMap(FirewallMapInterface):
    """Holds an application's firewalls, found by name or by matching a request.

    A firewall is matched to the first firewall whose request matcher claims
    the request, in the order they were registered, so a narrow firewall must
    be registered before a catch-all it would shadow.

    Each firewall is paired with a
    :class:`~xtr_http_foundation.request_matcher_interface.RequestMatcherInterface`
    from `xtr-http-foundation` — a path, host, method, address or callable
    matcher, or a chain of them — so the map matches a request without a
    notion of matching of its own. A chain of no matchers claims every
    request, the catch-all a firewall registered last relies on.

    The contexts it holds are read through
    :class:`~xtr_security_http.firewall_context_interface.FirewallContextInterface`,
    so the map works over whatever concrete context the bundle gathers. The
    listener chain, the exception listener and the logout listener a request's
    firewall runs are read off that context, so the map answers a request with
    the parts the firewall that runs them needs, without a notion of how the
    bundle ordered the chain.
    """

    __slots__ = ("_by_name", "_matchers")

    def __init__(
        self,
        firewalls: Sequence[tuple[RequestMatcherInterface, FirewallContextInterface]] = (),
    ) -> None:
        """Record the firewalls, keyed by name and kept in matching order.

        Raises:
            InvalidArgumentError: When two firewalls share a name.
        """
        self._matchers: tuple[tuple[RequestMatcherInterface, FirewallContextInterface], ...] = (
            tuple(firewalls)
        )
        self._by_name: dict[str, FirewallContextInterface] = {}
        for _, context in self._matchers:
            if context.name in self._by_name:
                raise InvalidArgumentError(f'Two firewalls share the name "{context.name}".')
            self._by_name[context.name] = context

    @override
    def has(self, name: str) -> bool:
        """Tell whether a firewall is registered under ``name``."""
        return name in self._by_name

    @override
    def get(self, name: str) -> FirewallContextInterface:
        """Return the firewall named ``name``.

        Raises:
            UnknownFirewallError: When no firewall carries that name.
        """
        try:
            return self._by_name[name]
        except KeyError as error:
            raise UnknownFirewallError(name, tuple(self._by_name)) from error

    @override
    async def match(self, request: ServerRequestInterface) -> FirewallContextInterface | None:
        """Return the first firewall whose matcher claims ``request``, or ``None``."""
        for matcher, context in self._matchers:
            if await matcher.matches(request):
                return context
        return None

    @override
    async def get_listeners(
        self,
        request: ServerRequestInterface,
    ) -> tuple[
        tuple[FirewallListenerInterface, ...],
        ExceptionListener | None,
        FirewallListenerInterface | None,
    ]:
        """Return the matched firewall's chain, exception listener and logout listener.

        A request no firewall claims answers an empty chain and no exception or
        logout listener — the firewall that runs the chain then has nothing to
        run, and no listener to answer an error or a logout with.
        """
        context = await self.match(request)
        if context is None:
            return ((), None, None)
        return (context.listeners, context.exception_listener, context.logout_listener)

    @override
    def names(self) -> tuple[str, ...]:
        """Return the names of every firewall registered."""
        return tuple(self._by_name)
