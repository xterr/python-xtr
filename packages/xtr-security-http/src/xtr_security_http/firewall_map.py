"""The firewalls of an application: found by name, or by matching a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from .exception.unknown_firewall_error import UnknownFirewallError
from .firewall_map_interface import FirewallMapInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from starlette.requests import Request

    from .firewall_context_interface import FirewallContextInterface
    from .request_matcher.request_matcher_interface import RequestMatcherInterface

__all__ = ["FirewallMap"]


@final
class FirewallMap(FirewallMapInterface):
    """Holds an application's firewalls, found by name or by matching a request.

    A firewall bound by name — ``Firewall("api")`` — is looked up directly. An
    unbound firewall — ``Firewall()`` — is matched to the first firewall whose
    request matcher claims the request, in the order they were registered, so a
    narrow firewall must be registered before a catch-all it would shadow.

    Each firewall is paired with a
    :class:`~xtr_security_http.request_matcher.request_matcher_interface.RequestMatcherInterface`
    — a path, host, method or callable matcher, or a chain of them, from the
    ``request_matcher`` package — so the map matches a request without a notion
    of matching of its own. A chain of no matchers claims every request, the
    catch-all a firewall registered last relies on.

    The contexts it holds are read through
    :class:`~xtr_security_http.firewall_context_interface.FirewallContextInterface`,
    so the map works over whatever concrete context the bundle gathers.
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
    def match(self, request: Request) -> FirewallContextInterface | None:
        """Return the first firewall whose matcher claims ``request``, or ``None``."""
        for matcher, context in self._matchers:
            if matcher.matches(request):
                return context
        return None

    @override
    def names(self) -> tuple[str, ...]:
        """Return the names of every firewall registered."""
        return tuple(self._by_name)
