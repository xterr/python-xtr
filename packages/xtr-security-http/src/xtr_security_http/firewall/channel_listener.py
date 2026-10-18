"""The chain step that moves a request onto the scheme its matched rule demands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_http_kernel.bridge import Response as FrameworkResponse
from xtr_http_kernel.bridge import StarletteHttpFactoryInterface
from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_logging_contracts import NullLogger

from .abstract_listener import AbstractListener

if TYPE_CHECKING:
    from xtr_http_kernel.event.request_event import RequestEvent
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_logging_contracts import LoggerInterface

    from xtr_security_http.access_map_interface import AccessMapInterface

__all__ = ["ChannelListener"]

#: The port each scheme answers on by default: the port a redirect to that
#: scheme leaves unspoken when the configured one is the default.
_HTTP_PORT: Final = 80
_HTTPS_PORT: Final = 443


@final
class ChannelListener(AbstractListener):
    """Redirects a request onto the scheme its matched rule demands it arrive over.

    A chain step over the access map's channel half — the same rules the
    access step decides attributes from, asked the same question.
    ``supports`` reads the channel the request's matched rule demands and
    answers ``True`` when the request did not arrive over it: ``https``
    demanded of a plain request, ``http`` of an encrypted one. Every other
    answer — no rule matched, the rule demands no channel, the request
    already carries the demanded one — is ``False``, the strict skip: the
    step parks nothing, so a request with nothing to change has nothing to
    come back for. ``authenticate`` answers the request with a permanent
    redirect to the same request over the demanded scheme, which is also
    what stops the chain.

    The scheme a request is read by is its URI's own — the connection's
    answer, not a forwarded header's claim; this stack has no
    trusted-proxy machinery to weigh one, so a proxy terminating the
    encryption in front of the server leaves the request reading plain and
    the redirect this step builds would loop. The step says so in its log
    when the forwarded headers claim the request was encrypted already.

    The redirect keeps everything but the scheme: the host, the whole path
    with its query string, and the port the *target* scheme is configured
    to answer on — spelled out only when it is not that scheme's default,
    so a redirect to plain ``https`` names no port while one to ``https``
    on ``8443`` does. The port the request itself arrived on is left
    behind: the target scheme has a port of its own.
    """

    __slots__ = ("_access_map", "_bridge", "_http_port", "_https_port", "_logger", "_responses")

    def __init__(  # noqa: PLR0913 -- the upstream listener's own shape, plus the response factory and bridge this stack answers with
        self,
        access_map: AccessMapInterface,
        responses: ResponseFactoryInterface,
        bridge: StarletteHttpFactoryInterface,
        *,
        logger: LoggerInterface | None = None,
        http_port: int = _HTTP_PORT,
        https_port: int = _HTTPS_PORT,
    ) -> None:
        """Build the step over the firewall's rules and what it answers with.

        Args:
            access_map: The firewall's rules, whose matched rule names the
                scheme the request must arrive over.
            responses: Builds the redirect, so the class names no response
                class.
            bridge: Turns the redirect — a pure message — into one the
                event accepts.
            logger: Writes the step's redirects, when given.
            http_port: The port plain ``http`` answers on; spelled out in a
                redirect to ``http`` when it is not ``80``.
            https_port: The port ``https`` answers on; spelled out in a
                redirect to ``https`` when it is not ``443``.
        """
        self._access_map = access_map
        self._responses = responses
        self._bridge = bridge
        self._logger = logger or NullLogger()
        self._http_port = http_port
        self._https_port = https_port

    @override
    async def supports(self, request: ServerRequestInterface) -> bool | None:
        """Answer whether the matched rule demands a scheme the request lacks.

        Only the channel half of the map's answer is weighed — the
        attributes are the access step's to decide — and the scheme is the
        request's own, the one its URI carries.
        """
        _attributes, channel = await self._access_map.get_patterns(request)
        scheme = request.get_uri().get_scheme()
        if channel == "https" and scheme != "https":
            self._log_https_redirect(request)
            return True
        if channel == "http" and scheme == "https":
            self._logger.info("Redirecting to HTTP.")
            return True
        return False

    @override
    async def authenticate(self, request_event: RequestEvent) -> None:
        """Answer the request with a permanent redirect to the demanded scheme.

        The redirect is built as a message and set on the event through the
        bridge — the kernel's rule for messages from elsewhere — which is
        also what stops the chain: the steps after this one would be
        deciding about a request already answered.
        """
        await self._answer(request_event, self._redirect_for(request_event.request))

    def _log_https_redirect(self, request: ServerRequestInterface) -> None:
        """Write the redirect to ``https``, naming a proxy when the headers blame one.

        The forwarded headers are read to pick the message, not to change
        the answer: a request that reached the server over plain ``http``
        while its headers claim an encrypted proxy in front is the one case
        the redirect this step builds would loop, so the log points at it.
        """
        if request.get_header_line("X-Forwarded-Proto") == "https":
            self._logger.info(
                'Redirecting to HTTPS. ("X-Forwarded-Proto" header is set to "https" '
                "- the request reached the server over plain http; check the proxy "
                "in front of it.)",
            )
        elif "proto=https" in request.get_header_line("Forwarded"):
            self._logger.info(
                'Redirecting to HTTPS. ("Forwarded" header is set to "proto=https" '
                "- the request reached the server over plain http; check the proxy "
                "in front of it.)",
            )
        else:
            self._logger.info("Redirecting to HTTPS.")

    def _redirect_for(self, request: ServerRequestInterface) -> ResponseInterface:
        """Return the permanent redirect to the same request over the other scheme.

        The scheme is the flip of the one the request arrived over — the
        demanded one, since the step only runs when the two differ — and
        the port is the target scheme's own, the request's left behind.
        """
        uri = request.get_uri()
        scheme = "http" if uri.get_scheme() == "https" else "https"
        if scheme == "http" and self._http_port != _HTTP_PORT:
            port = f":{self._http_port}"
        elif scheme == "https" and self._https_port != _HTTPS_PORT:
            port = f":{self._https_port}"
        else:
            port = ""
        query = uri.get_query()
        asked = f"?{query}" if query else ""
        url = f"{scheme}://{uri.get_host()}{port}{uri.get_path()}{asked}"
        return self._responses.create_response(301).with_header("location", url)

    async def _answer(self, request_event: RequestEvent, response: ResponseInterface) -> None:
        """Set ``response`` on ``request_event`` as what the lifecycle can send.

        The kernel's own response is both a message and what the framework
        sends, so it is set as it is; a pure message is converted through
        the bridge, the kernel's rule for messages from elsewhere.
        """
        if isinstance(response, FrameworkResponse):
            request_event.set_response(response)
            return
        request_event.set_response(await self._bridge.create_response(response))
