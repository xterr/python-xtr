"""Puts the debug toolbar into every profiled HTML page as it streams out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, cast, final

from markupsafe import Markup
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import Request
from starlette.routing import NoMatchFound

from .controller.profiler_controller import PROFILER_PAGE_HEADER

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from .bundle.web_profiler_config import WebProfilerConfig
    from .csp.content_security_policy_handler import ContentSecurityPolicyHandler
    from .profiler.template_manager import TemplateManager

__all__ = ["WebDebugToolbarMiddleware"]

_BODY_END: Final = b"</body>"
_CARRY: Final = len(_BODY_END) - 1
_REDIRECTION: Final = range(300, 400)
_TOKEN_HEADER: Final = "x-debug-token"  # noqa: S105 — a header name, not a secret
_DOCUMENTS: Final = frozenset({"document", "iframe", "frame", "embed", "object"})
_SNIPPET: Final = "@xtr_web_profiler/profiler/toolbar_js.html.j2"
_REDIRECT_PAGE: Final = "@xtr_web_profiler/profiler/toolbar_redirect.html.j2"


@final
class WebDebugToolbarMiddleware:
    """Names each profile on its response, and draws the toolbar into the HTML pages.

    Every response naming a profile in ``X-Debug-Token`` also gets
    ``X-Debug-Token-Link``, the address of its profile — what a client that
    renders no HTML follows. A background request (``X-Requested-With:
    XMLHttpRequest``, or a fetch the browser marks as not loading a document)
    never gets the toolbar; with ``ajax_replace`` its response asks the page
    to reload the toolbar with its own profile.

    The toolbar is drawn into a response only when all of these hold: the
    toolbar is on, the response names a profile, it is no redirect, its
    content type is HTML, it is no attachment, its body is not encoded, and
    the request was not a background one. It goes in before the closing
    ``</body>`` — found even when the tag is split across two chunks of a
    streamed body — and the ``Content-Length`` is dropped, the body having
    grown. A page with no ``</body>`` goes out unchanged.

    With ``intercept_redirects``, a redirect answering a page is replaced by
    a page saying where it leads, toolbar included, so the request that
    redirected can be read before following it.

    The profiler's own pages run under no content security policy; any
    other page drawn into has the toolbar's nonces added to its policy.
    """

    __slots__ = ("_app", "_config", "_csp", "_manager")

    def __init__(
        self,
        app: ASGIApp,
        *,
        config: WebProfilerConfig,
        manager: TemplateManager,
        csp: ContentSecurityPolicyHandler,
    ) -> None:
        """Wrap ``app``.

        Args:
            app: The application whose pages get the toolbar.
            config: Whether the toolbar is on, and how it behaves.
            manager: What renders the toolbar's loader and the redirect page.
            csp: What lets the toolbar run under a page's policy.
        """
        self._app = app
        self._config = config
        self._manager = manager
        self._csp = csp

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve the request, drawing the toolbar into its response when it qualifies."""
        if cast("str", scope["type"]) != "http":
            await self._app(scope, receive, send)
            return
        await self._app(scope, receive, _Exchange(self, scope, send).send)

    def snippet(self, scope: Scope, token: str, nonces: dict[str, str]) -> bytes | None:
        """Return the toolbar's loader for the profile ``token``, or ``None`` when unrouted."""
        request = Request(scope)
        try:
            context = {
                "token": token,
                "toolbar_url": str(request.url_for("_wdt", token=token)),
                "stylesheet_url": str(request.url_for("_wdt_stylesheet")),
                "profiler_url": str(request.url_for("_profiler", token=token)),
                "excluded_ajax_paths": self._config.excluded_ajax_paths,
                "ajax_replace": self._config.ajax_replace,
                **nonces,
            }
        except NoMatchFound:
            return None
        return self._manager.render(_SNIPPET, context).encode()

    def redirect_page(self, location: str, status: int, snippet: bytes) -> bytes:
        """Return the page standing in for a redirect to ``location``."""
        context = {
            "location": location,
            "status_code": status,
            "toolbar": Markup(snippet.decode()),  # noqa: S704 — rendered by the escaping environment
        }
        return self._manager.render(_REDIRECT_PAGE, context).encode()

    @property
    def config(self) -> WebProfilerConfig:
        """How the toolbar behaves."""
        return self._config

    @property
    def csp(self) -> ContentSecurityPolicyHandler:
        """What lets the toolbar run under a page's policy."""
        return self._csp


@final
class _Exchange:
    """One request's response, passed through, drawn into, or replaced."""

    __slots__ = ("_carry", "_injected", "_middleware", "_mode", "_scope", "_send", "_snippet")

    def __init__(self, middleware: WebDebugToolbarMiddleware, scope: Scope, send: Send) -> None:
        self._middleware = middleware
        self._scope = scope
        self._send = send
        self._mode = "pass"
        self._snippet = b""
        self._carry = b""
        self._injected = False

    async def send(self, message: Message) -> None:
        message_type = cast("str", message["type"])
        if message_type == "http.response.start":
            await self._start(message)
        elif message_type == "http.response.body" and self._mode == "inject":
            await self._body(message)
        elif message_type == "http.response.body" and self._mode == "replaced":
            return
        else:
            await self._send(message)

    async def _start(self, message: Message) -> None:
        middleware = self._middleware
        config = middleware.config
        headers = MutableHeaders(scope=message)
        request_headers = Headers(scope=self._scope)
        if PROFILER_PAGE_HEADER.lower() in headers:
            del headers[PROFILER_PAGE_HEADER]
            middleware.csp.disable_csp(headers)
            await self._send(message)
            return
        token = headers.get(_TOKEN_HEADER)
        if token is not None:
            self._link(headers, token)
        background = _is_background(request_headers)
        if background and config.ajax_replace and token is not None:
            headers["X-Debug-Toolbar-Replace"] = "1"
        if background or token is None:
            await self._send(message)
            return
        status = cast("int", message["status"])
        nonces = middleware.csp.get_nonces(request_headers)
        if (
            config.intercept_redirects
            and status in _REDIRECTION
            and "location" in headers
            and "html" in request_headers.get("accept", "")
        ):
            await self._replace(message, headers, token, nonces)
            return
        if not config.toolbar or not _drawable(status, headers):
            await self._send(message)
            return
        snippet = middleware.snippet(self._scope, token, nonces)
        if snippet is None:
            await self._send(message)
            return
        self._snippet = snippet
        self._mode = "inject"
        if "content-length" in headers:
            del headers["content-length"]
        middleware.csp.update_response_headers(nonces, headers)
        await self._send(message)

    def _link(self, headers: MutableHeaders, token: str) -> None:
        """Name the address of the profile ``token`` on the response."""
        try:
            headers["X-Debug-Token-Link"] = str(
                Request(self._scope).url_for("_profiler", token=token)
            )
        except NoMatchFound:
            headers["X-Debug-Error"] = "the profiler routes are not included"

    async def _replace(
        self, message: Message, headers: MutableHeaders, token: str, nonces: dict[str, str]
    ) -> None:
        snippet = self._middleware.snippet(self._scope, token, nonces) or b""
        location = headers["location"]
        page = self._middleware.redirect_page(location, cast("int", message["status"]), snippet)
        kept = [
            (name, value)
            for name, value in headers.raw
            if name.lower() not in {b"location", b"content-length", b"content-type"}
        ]
        self._mode = "replaced"
        await self._send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    *kept,
                    (b"content-type", b"text/html; charset=utf-8"),
                    (b"content-length", str(len(page)).encode()),
                ],
            }
        )
        await self._send({"type": "http.response.body", "body": page, "more_body": False})

    async def _body(self, message: Message) -> None:
        chunk = self._carry + cast("bytes", message.get("body", b""))
        more = cast("bool", message.get("more_body", False))
        self._carry = b""
        if not self._injected:
            lowered = chunk.lower()
            position = lowered.find(_BODY_END) if more else lowered.rfind(_BODY_END)
            if position >= 0:
                chunk = chunk[:position] + self._snippet + chunk[position:]
                self._injected = True
            elif more:
                # The closing tag may be split across this chunk and the next.
                chunk, self._carry = chunk[:-_CARRY], chunk[-_CARRY:]
        await self._send({"type": "http.response.body", "body": chunk, "more_body": more})


def _is_background(headers: Headers) -> bool:
    if headers.get("x-requested-with", "").lower() == "xmlhttprequest":
        return True
    destination = headers.get("sec-fetch-dest")
    return destination is not None and destination not in _DOCUMENTS


def _drawable(status: int, headers: MutableHeaders) -> bool:
    return (
        status not in _REDIRECTION
        and "html" in headers.get("content-type", "")
        and "attachment" not in headers.get("content-disposition", "").lower()
        and "content-encoding" not in headers
    )
