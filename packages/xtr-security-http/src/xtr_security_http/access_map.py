"""The ordered access-control rules of a firewall, matched against a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .access_map_interface import AccessMapInterface

if TYPE_CHECKING:
    from xtr_http_foundation import RequestMatcherInterface
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["AccessMap"]


@final
class AccessMap(AccessMapInterface):
    """Holds a firewall's access-control rules and finds the first a request matches.

    A rule is a request matcher and the one attribute a claimed request must
    satisfy, added with :meth:`add`. Rules are tried in the order they were
    added; the first whose matcher claims the request decides it, so a broad
    ``^/api`` rule must be added after the narrow ``^/api/admin`` it would
    otherwise shadow. A request matching no rule has no attribute to satisfy —
    the firewall lets it through, its access left to whatever the route itself
    requires.

    :meth:`get_patterns` answers the rule's attribute as the one member of a
    tuple, beside the channel the rule demands the request arrive over. A
    rule added without a channel demands none — the channel half of its
    answer is ``None`` — while one added with ``channel="https"`` is answered
    with a redirect until the request arrives over it.
    """

    __slots__ = ("_rules",)

    def __init__(self) -> None:
        """Start with no rules; add each with :meth:`add`."""
        self._rules: list[tuple[RequestMatcherInterface, str, str | None]] = []

    def add(
        self,
        request_matcher: RequestMatcherInterface,
        attribute: str,
        channel: str | None = None,
    ) -> None:
        """Append a rule: ``attribute`` is required of a request ``request_matcher`` claims.

        One attribute per rule is deliberate — a rule that needs two conditions
        is two rules, or a single closure attribute.

        ``channel`` names the scheme the rule demands the request arrive
        over — ``"https"`` or ``"http"`` — or ``None`` to demand none; the
        channel listener answers a request arriving over the wrong one with a
        redirect to the same request over the scheme the rule demands.
        """
        self._rules.append((request_matcher, attribute, channel))

    @override
    async def get_patterns(
        self, request: ServerRequestInterface
    ) -> tuple[tuple[str, ...], str | None]:
        """Return the first matching rule's attribute, and the channel it demands.

        The attribute rides out as the one member of a tuple, the shape the
        deciding step hands the access decision manager; the channel is the
        one the matching rule demands, or ``None`` when it demands none.
        """
        for request_matcher, attribute, channel in self._rules:
            if await request_matcher.matches(request):
                return (attribute,), channel
        return (), None
