"""The parser each configured webhook type is read by, reached through the container."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_webhook.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

    from xtr_dependency_injection import ServiceLocator

    from xtr_webhook.client.request_parser_interface import RequestParserInterface

__all__ = ["ROUTE_QUALIFIER", "RoutedParsers"]

#: The qualifier each configured type's parser is aliased under. Apart from the
#: bundle's own ``webhook`` qualifier, so a type named ``webhook`` reads with the
#: parser its route names, and no type is served that routing did not name.
ROUTE_QUALIFIER: Final = "webhook.route.{type}"


@final
class RoutedParsers(ServiceProviderInterface["RequestParserInterface"]):
    """Hands the controller the parser of each type the routing names, and no other.

    The container's locator over every parser is filtered down to the types
    the routing names, each reached under its own qualifier, so a parser — and
    what it needs — is built the first time a webhook of its type arrives.
    """

    __slots__ = ("_locator", "_qualifiers")

    def __init__(
        self,
        locator: ServiceLocator[RequestParserInterface],
        types: tuple[str, ...],
    ) -> None:
        """Serve ``types``, each read through ``locator`` under its route's qualifier."""
        self._locator = locator
        self._qualifiers = {name: ROUTE_QUALIFIER.format(type=name) for name in types}

    @override
    async def get(self, name: Hashable, /) -> RequestParserInterface:
        """Return the parser reading webhooks of the type ``name``.

        Raises:
            LogicError: If the routing names no such type. The endpoint asks
                :meth:`has` first and answers 404 itself.
        """
        qualifier = self._qualifiers.get(str(name))
        if qualifier is None:
            raise LogicError(f'Unable to find a parser for the webhook type "{name}".')
        return await self._locator.get(qualifier)

    @override
    def has(self, name: Hashable, /) -> bool:
        return str(name) in self._qualifiers

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        provided = self._locator.provided_services()
        return MappingProxyType(
            {name: provided[qualifier] for name, qualifier in self._qualifiers.items()}
        )
