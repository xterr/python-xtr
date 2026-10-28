"""Matching paths, generating URIs and building redirects, over request messages.

The helpers the stateful half of the security layer leans on — a form login
asking whether this request is its login path, a logout redirect, a
remember-me cookie's target — gathered behind one service the bundle wires
once. Everything here reads the request as a message and builds answers
through the response factory, so the class names neither a framework request
nor a response class.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Final, final
from urllib.parse import unquote, urlsplit

from xtr_http_message_contracts.factory import (
    ResponseFactoryInterface,  # noqa: TC002 -- the container reads this constructor parameter's type at runtime
)
from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface

__all__ = ["HttpUtils"]

#: An absolute URL at the head of a path — the part a redirect-target check
#: weighs. Written the tolerant way the upstream check is: two or more
#: slashes or backslashes after the scheme, so the ``http:\/\/`` spellings a
#: browser may still resolve are refused rather than slipped past.
_ABSOLUTE_URL: Final = re.compile(r"^https?:[/\\]{2,}+[^/]+", re.IGNORECASE)

#: The port each scheme answers on by default; a host carrying one of these
#: needs no ``:port`` of its own.
_DEFAULT_PORTS: Final[dict[str, int]] = {"http": 80, "https": 443, "ws": 80, "wss": 443}


def _plain_path(path: str) -> str:
    """Return ``path`` as it is: the URI of a path is the path.

    The default URI builder. A ``Location`` header may carry a path, and the
    framework resolves it against the request's own host; an application that
    wants absolute URIs injects a builder that writes them.
    """
    return path


def _is_absolute(path: str) -> bool:
    """Tell whether ``path`` already is an absolute URL."""
    parsed = urlsplit(path)
    return parsed.scheme != "" and parsed.netloc != ""


@final
class HttpUtils:
    """Encapsulates the logic needed to redirect the caller, and to match paths.

    A path is always a literal path — an absolute path (``/login``) or an
    absolute URL (``https://…``) — never a route name: this stack has no
    routing component to resolve one by, the recorded deviation, so a
    relative path is refused as the configuration mistake it is here. The URI
    a path becomes is written by the injected URI builder — the path itself
    by default, an absolute URL when the application's builder writes one.

    Attributes:
        domain_regexp: A regexp the target of an HTTP redirection must match,
            scheme included, with a ``%s`` slot for the request's host.
        secure_domain_regexp: The same, weighed only when the request arrived
            over ``https``.
    """

    __slots__ = ("_domain_regexp", "_responses", "_secure_domain_regexp", "_uri_builder")

    def __init__(
        self,
        responses: ResponseFactoryInterface,
        uri_builder: Callable[[str], str] | None = None,
        domain_regexp: str | None = None,
        secure_domain_regexp: str | None = None,
    ) -> None:
        """Record the response factory, the URI builder and the redirect-target guards.

        Args:
            responses: Builds the redirect responses, so the class names no
                response class.
            uri_builder: Writes the URI a path becomes. Left out, a path is
                its own URI — a ``Location`` may carry one, and the framework
                resolves it against the request's host.
            domain_regexp: A regexp the target of an HTTP redirection must
                match, scheme included, with a ``%s`` slot for the request's
                host; a target that fails it is replaced by ``/``. ``None``
                allows any target.
            secure_domain_regexp: The same, weighed only when the request
                arrived over ``https``. ``None`` allows any target.
        """
        self._responses = responses
        self._uri_builder = _plain_path if uri_builder is None else uri_builder
        self._domain_regexp = domain_regexp
        self._secure_domain_regexp = secure_domain_regexp

    def check_request_path(self, request: ServerRequestInterface, path: str) -> bool:
        """Tell whether ``path`` is the path of ``request``.

        The request's path is read as it travels — percent-decoded — and
        compared with the configured one, which is the whole path the message
        carries: the same path a firewall's matcher matches, so an application
        mounted under a prefix configures its paths with the prefix, the one
        place this stack records where the application begins.

        Raises:
            InvalidArgumentError: When ``path`` is not an absolute path or an
                absolute URL — a route name, which no routing component here
                can resolve.
        """
        if not path.startswith("/"):
            raise InvalidArgumentError(
                f"The path {path!r} is not an absolute path; route names are not supported, "
                "only literal paths.",
            )
        return path == unquote(request.get_uri().get_path())

    def generate_uri(self, path: str) -> str:
        """Generate a URI, based on the given path or absolute URL.

        An empty path or an absolute URL is returned as it is; an absolute
        path goes through the URI builder; anything else is a route name,
        which nothing here can resolve.

        Raises:
            InvalidArgumentError: When ``path`` is neither an absolute path
                nor an absolute URL.
        """
        if path == "" or _is_absolute(path):
            return path
        if not path.startswith("/"):
            raise InvalidArgumentError(
                f"The path {path!r} is not an absolute path; route names are not supported, "
                "only literal paths.",
            )
        return self._uri_builder(path)

    def create_redirect_response(
        self,
        request: ServerRequestInterface,
        path: str,
        status: int = 302,
    ) -> ResponseInterface:
        """Create a redirect response to ``path``, answering with ``status``.

        A target that names another host is weighed against the configured
        domain regexps first — the ``secure`` one while the request arrived
        over ``https`` — and a target neither allows is replaced by ``/``,
        so a redirect can never leave the application's own domain by the
        word of a path an attacker chose.
        """
        if self._secure_domain_regexp is not None and request.get_uri().get_scheme() == "https":
            path = self._guarded(self._secure_domain_regexp, request, path)
        if self._domain_regexp is not None:
            path = self._guarded(self._domain_regexp, request, path)
        return self._responses.create_response(status).with_header(
            "location",
            self.generate_uri(path),
        )

    def _guarded(self, regexp: str, request: ServerRequestInterface, path: str) -> str:
        """Return ``path``, or ``/`` when it names a host ``regexp`` does not allow.

        Raises:
            InvalidArgumentError: When ``regexp`` is not a valid regular
                expression.
        """
        target = _ABSOLUTE_URL.search(path)
        if target is None:
            return path
        allowed = regexp.replace("%s", re.escape(_host_of(request)))
        if re.match(allowed, target.group(0)) is not None:
            return path
        return "/"


def _host_of(request: ServerRequestInterface) -> str:
    """Return the host the request was addressed to, port included when not the default."""
    uri = request.get_uri()
    host = uri.get_host()
    port = uri.get_port()
    if port is None or port == _DEFAULT_PORTS.get(uri.get_scheme() or "http"):
        return host
    return f"{host}:{port}"
