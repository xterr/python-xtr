"""Parsers already built, handed over by the type of webhook each reads."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_webhook.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from xtr_webhook.client import RequestParserInterface

__all__ = ["BuiltParsers"]


@final
class BuiltParsers(ServiceProviderInterface["RequestParserInterface"]):
    """Hands over parsers from a mapping — what stands in where there is no container.

    The controller asks for a parser by type and does not care where it came
    from: a container's locator, which builds each parser with its own
    dependencies the first time a webhook for it arrives, or a mapping of
    parsers built by hand. This is the second of those, so the controller has
    one thing to ask rather than two.
    """

    __slots__ = ("_parsers",)

    def __init__(self, parsers: Mapping[str, RequestParserInterface]) -> None:
        """Hand over ``parsers``, by the type of webhook each reads.

        The mapping is copied: which parser speaks for a type is fixed once
        the endpoint is built, so a caller still writing to its own dict
        cannot change who reads a subscriber's webhooks halfway through a
        deploy's life.
        """
        self._parsers = dict(parsers)

    @override
    async def get(self, name: Hashable, /) -> RequestParserInterface:
        """Return the parser reading webhooks of the type ``name``.

        Raises:
            LogicError: If there is none. The endpoint asks :meth:`has` first
                and answers 404 itself, so reaching this means the two were
                asked different questions — a mistake in the code, not a
                webhook naming a type nobody subscribed to.
        """
        parser = self._parsers.get(str(name))
        if parser is None:
            raise LogicError(f'Unable to find a parser for the webhook type "{name}".')
        return parser

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._parsers

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType({name: type(parser) for name, parser in self._parsers.items()})
