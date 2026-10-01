"""The ordered access-control rules of a firewall, matched against a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .access_map_interface import AccessMapInterface

if TYPE_CHECKING:
    from starlette.requests import Request

    from .request_matcher.request_matcher_interface import RequestMatcherInterface

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
    """

    __slots__ = ("_rules",)

    def __init__(self) -> None:
        """Start with no rules; add each with :meth:`add`."""
        self._rules: list[tuple[RequestMatcherInterface, str]] = []

    def add(self, request_matcher: RequestMatcherInterface, attribute: str) -> None:
        """Append a rule: ``attribute`` is required of a request ``request_matcher`` claims.

        One attribute per rule is deliberate — a rule that needs two conditions
        is two rules, or a single closure attribute.
        """
        self._rules.append((request_matcher, attribute))

    @override
    def get_attribute(self, request: Request) -> str | None:
        """Return the attribute the first matching rule requires, or ``None``."""
        for request_matcher, attribute in self._rules:
            if request_matcher.matches(request):
                return attribute
        return None
