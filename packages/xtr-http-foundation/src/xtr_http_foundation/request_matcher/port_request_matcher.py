"""A matcher over the port a request was asked of."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_http_foundation.request_matcher_interface import RequestMatcherInterface

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

__all__ = ["PortRequestMatcher"]

_SECURE_SCHEME: Final = "https"
_SECURE_PORT: Final = 443
_PORT: Final = 80


def _port(request: ServerRequestInterface) -> int:
    """Return the port ``request`` was asked of, named or implied.

    A URI leaves the port out when it is the standard one of its scheme, since
    it says nothing the scheme does not — so the port a rule is written about is
    the one the scheme stands for whenever the URI is silent.
    """
    named = request.get_uri().get_port()
    if named is not None:
        return named

    return _SECURE_PORT if request.get_uri().get_scheme() == _SECURE_SCHEME else _PORT


@final
class PortRequestMatcher(RequestMatcherInterface):
    """Claims a request asked of one port.

    This is the rule for an application answering on more than one port — a
    public one and an administrative one — where which of them a request arrived
    on is the whole of what separates them.
    """

    __slots__ = ("_port",)

    def __init__(self, port: int) -> None:
        """Record the port a request has to have been asked of.

        Args:
            port: The port.
        """
        self._port = port

    @override
    async def matches(self, request: ServerRequestInterface) -> bool:
        """Tell whether ``request`` was asked of this matcher's port."""
        return _port(request) == self._port
