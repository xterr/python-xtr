"""A request as it arrived, with everything the server learned alongside it."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Self, TypeVar, final
from urllib.parse import parse_qsl

from typing_extensions import override
from xtr_http_message_contracts import ServerRequestInterface

from ._request_trait import RequestTrait
from .exception import InvalidArgumentError
from .uri import Uri

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface, UriInterface

__all__ = ["ServerRequest"]

_HOST = "Host"

_K = TypeVar("_K")
_V = TypeVar("_V")


def _held(given: Mapping[_K, _V]) -> Mapping[_K, _V]:
    """Return the mapping to hold for one given to the request.

    A mapping nobody can change is held as it is: copying it would only cost a
    read of every entry, and would turn whatever kind of mapping it is — one
    that answers every value of a repeated name, say — into a plain one that
    answers a single value per name. A mutable mapping is copied, since the
    caller keeps a reference to it and a request must not change behind
    whoever was handed it.

    Args:
        given: The mapping the caller passed.

    Returns:
        The mapping itself when it cannot be changed, otherwise a copy of it.
    """
    return dict(given) if isinstance(given, MutableMapping) else given


def _parse_query(query: str) -> dict[str, object]:
    """Read a query string into parameters, the last of a repeated name winning.

    Args:
        query: The query string, without its leading ``?``.

    Returns:
        Each parameter name mapped to its value. A name with no value reads as
        an empty string rather than being dropped, since whether a parameter
        was sent at all is often the question.
    """
    return dict(parse_qsl(query, keep_blank_values=True))


@final
class ServerRequest(RequestTrait, ServerRequestInterface):
    """An incoming, server-side request.

    On top of what every request carries, this one gathers what reached the
    application with it: the parameters of the environment it arrived in, the
    cookies, the query string parsed, the files that came with it and the body
    parsed into parameters — plus the attributes a handler annotates it with
    as it works out who sent it and what they asked for.

    ```python
    from xtr_http_message import ServerRequest

    request = ServerRequest("GET", "/orders?page=2")
    assert request.get_query_params() == {"page": "2"}
    assert request.with_attribute("user", "ada").get_attribute("user") == "ada"
    ```

    The query parameters are read off the URI as the request is built; nothing
    keeps them in step with it afterwards, so a URI changed later leaves them
    as they were — which is what lets a handler correct them.

    The cookies, the query parameters and the uploaded files are held exactly
    as they were given when nothing can change them — a mapping that is not a
    :class:`~collections.abc.MutableMapping` — and copied when they can. So a
    mapping of a kind that answers more than a single value per name reaches
    whoever reads it back as that kind, rather than flattened into a plain
    one.
    """

    __slots__ = (
        "_attributes",
        "_cookie_params",
        "_parsed_body",
        "_query_params",
        "_server_params",
        "_uploaded_files",
    )

    def __init__(
        self,
        method: str,
        uri: UriInterface | str,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        body: bytes | BinaryIO | StreamInterface | None = None,
        version: str = "1.1",
        server_params: Mapping[str, object] | None = None,
    ) -> None:
        """Build a server request.

        Args:
            method: The HTTP method, kept exactly as given.
            uri: The URI of the request. Given as text, it is read into a
                :class:`~xtr_http_message.uri.Uri`.
            headers: Each header name mapped to one value or to several.
            body: The payload, in any of the shapes a stream is built from.
                Left out, nothing is opened until the body is asked for.
            version: The HTTP version number alone.
            server_params: The parameters of the environment the request
                arrived in, taken exactly as given. ``None`` means none.

        Raises:
            InvalidArgumentError: When the URI cannot be read, or a header
                name or value is not one.
        """
        super().__init__()

        self._server_params: Mapping[str, object] = (
            {} if server_params is None else _held(server_params)
        )
        self._attributes: dict[str, object] = {}
        self._cookie_params: Mapping[str, str] = {}
        self._parsed_body: object | None = None
        self._uploaded_files: Mapping[str, object] = {}

        self._method = method
        self._uri = Uri(uri) if isinstance(uri, str) else uri
        self._set_headers(headers or {})
        self._protocol = version
        self._query_params: Mapping[str, object] = _parse_query(self._uri.get_query())

        if not self.has_header(_HOST):
            self._update_host_from_uri()

        self._set_body(body)

    @override
    def get_server_params(self) -> Mapping[str, object]:
        """Return the parameters of the environment the request arrived in.

        Returns:
            Each parameter under the name the environment gave it — the
            mapping as it was given where nothing can change it, otherwise a
            fresh one. Nothing changes them: they are the state the request
            arrived in.
        """
        return _held(self._server_params)

    @override
    def get_cookie_params(self) -> Mapping[str, str]:
        """Return the cookies the client sent.

        Returns:
            Each cookie name mapped to its value — the mapping as it was given
            where nothing can change it, otherwise a fresh one.
        """
        return _held(self._cookie_params)

    @override
    def with_cookie_params(self, cookies: Mapping[str, str]) -> Self:
        """Return an instance carrying ``cookies``.

        Neither the ``Cookie`` header of the new instance nor its environment
        parameters change with them.

        Args:
            cookies: Each cookie name mapped to its value.

        Returns:
            A new instance; this one is left as it was.
        """
        new = self._copy()
        new._cookie_params = _held(cookies)  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def get_query_params(self) -> Mapping[str, object]:
        """Return the query string, parsed into parameters.

        Returns:
            Each parameter name mapped to its value — the mapping as it was
            given where nothing can change it, otherwise a fresh one. These
            were read off the URI when the request was built and may have been
            replaced since; parse ``get_uri().get_query()`` to be sure of what
            arrived.
        """
        return _held(self._query_params)

    @override
    def with_query_params(self, query: Mapping[str, object]) -> Self:
        """Return an instance carrying ``query``.

        Neither the URI the request holds nor its environment parameters
        change with them.

        Args:
            query: Each parameter name mapped to its value.

        Returns:
            A new instance; this one is left as it was.
        """
        new = self._copy()
        new._query_params = _held(query)  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def get_uploaded_files(self) -> Mapping[str, object]:
        """Return the files that came with the request.

        Returns:
            A mapping shaped like the names the files were submitted under,
            every leaf of it an uploaded file — the mapping as it was given
            where nothing can change it, otherwise a fresh one. Empty when no
            file came with the request.
        """
        return _held(self._uploaded_files)

    @override
    def with_uploaded_files(self, uploaded_files: Mapping[str, object]) -> Self:
        """Return an instance carrying ``uploaded_files``.

        Args:
            uploaded_files: A tree of uploaded files, shaped as
                :meth:`get_uploaded_files` describes.

        Returns:
            A new instance; this one is left as it was.
        """
        new = self._copy()
        new._uploaded_files = _held(uploaded_files)  # noqa: SLF001 — a copy of this class.

        return new

    @override
    def get_parsed_body(self) -> object | None:
        """Return the parameters found in the body of the request.

        Returns:
            Whatever parsing the body yielded, or ``None`` when nothing has
            been parsed into the request.
        """
        return self._parsed_body

    @override
    def with_parsed_body(self, data: object | None) -> Self:
        """Return an instance carrying ``data`` as its body parameters.

        Args:
            data: The parsed body parameters — a mapping, or an object
                standing for the structure the body held — or ``None`` when
                there was nothing to parse.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            InvalidArgumentError: When the data is a scalar: parsing a body
                yields structure, so a number or a string cannot be what it
                yielded.
        """
        if isinstance(data, (bool, bytes, complex, float, int, str)):
            raise InvalidArgumentError(
                "First parameter to with_parsed_body MUST be object, mapping or None"
            )

        new = self._copy()
        new._parsed_body = data  # noqa: SLF001 — a copy of this very class.

        return new

    @override
    def get_attributes(self) -> Mapping[str, object]:
        """Return what was derived from the request while handling it.

        Returns:
            A fresh mapping of each attribute name to its value.
        """
        return dict(self._attributes)

    @override
    def get_attribute(self, name: str, default: object | None = None) -> object | None:
        """Return one of the attributes :meth:`get_attributes` describes.

        An attribute recorded as ``None`` is told apart from one that was
        never recorded: the first reads as ``None``, the second as
        ``default``.

        Args:
            name: The attribute name.
            default: What to answer with when the request carries no such
                attribute.

        Returns:
            The value under ``name``, or ``default``.
        """
        if name not in self._attributes:
            return default

        return self._attributes[name]

    @override
    def with_attribute(self, name: str, value: object) -> Self:
        """Return an instance carrying one more attribute.

        Args:
            name: The attribute name.
            value: The value to record under it.

        Returns:
            A new instance; this one is left as it was.
        """
        new = self._copy()
        new._attributes = {**self._attributes, name: value}  # noqa: SLF001 — a copy of this class.

        return new

    @override
    def without_attribute(self, name: str) -> Self:
        """Return an instance with the ``name`` attribute gone.

        Args:
            name: The attribute name.

        Returns:
            A new instance, or this one when the request carries no such
            attribute.
        """
        if name not in self._attributes:
            return self

        new = self._copy()
        new._attributes = {  # noqa: SLF001 — a copy of this very class.
            held: value for held, value in self._attributes.items() if held != name
        }

        return new
