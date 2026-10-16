"""A request as it arrived, with everything the server learned alongside it."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Self, TypeVar, final
from urllib.parse import parse_qsl

from typing_extensions import override
from xtr_http_message_contracts import ServerRequestInterface

from ._connected_trait import ConnectedTrait
from .exception import InvalidArgumentError
from .uri import Uri

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface, UriInterface

    from .request_source import RequestSource

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
class ServerRequest(ConnectedTrait, ServerRequestInterface):
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

    A request is also born connected, over a
    :class:`~xtr_http_message.request_source.RequestSource` — see
    :meth:`over`. Its head is passed eagerly; its body is one lazy stream
    that materialises on first read; its parsed body, uploaded files and
    attributes answer what the source has yielded so far, the attributes
    live. The ``with_*`` members of such a request detach: plain eager
    copies, so a change a handler makes never reaches the connection.
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

    @classmethod
    def over(
        cls,
        method: str,
        uri: UriInterface | str,
        *,
        source: RequestSource,
        body: bytes | BinaryIO | StreamInterface | None = None,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        server_params: Mapping[str, object] | None = None,
        cookies: Mapping[str, str] | None = None,
        query: Mapping[str, object] | None = None,
        protocol_version: str = "1.1",
    ) -> Self:
        """Build a server request over ``source``, born connected to it.

        The head is passed eagerly — it costs no input and never changes
        mid-request — and the body side comes from the source: the body
        is one lazy stream that materialises on its first read, and the
        parsed body and the uploaded files answer what materialisation
        has yielded so far.

        Args:
            method: The HTTP method, kept exactly as given.
            uri: The URI of the request. Given as text, it is read into a
                :class:`~xtr_http_message.uri.Uri`.
            source: Where the connected request reads its late answers
                from.
            body: Refused — the body of a request built over a source is
                the source's to materialise, and there is one owner of
                the body. The parameter exists so a caller used to the
                constructor's shape is told the rule rather than left
                with an unexpected keyword.
            headers: Each header name mapped to one value or to several.
                A header the message grammar refuses is left out rather
                than refusing the request: a connection let it through,
                and a message is no place to re-litigate that.
            server_params: The parameters of the environment the request
                arrived in, taken exactly as given.
            cookies: The cookies the client sent; left out, none.
            query: The query string, parsed into parameters; left out,
                the URI's own query stands.
            protocol_version: The HTTP version number alone.

        Returns:
            The request, connected to ``source``.

        Raises:
            InvalidArgumentError: When ``body`` is given alongside
                ``source``.
        """
        if body is not None:
            raise InvalidArgumentError(
                "One owner of the body: body= and source= cannot both be given"
            )

        request = cls(method, uri, None, None, protocol_version, server_params)
        for name, values in (headers or {}).items():
            try:
                request = request.with_header(name, values)
            except ValueError:
                continue

        if cookies is not None:
            request = request.with_cookie_params(cookies)
        if query is not None:
            request = request.with_query_params(query)

        request._source = source  # noqa: SLF001 — a fresh instance of this very class.
        return request

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
            file came with the request. A request built over a connection
            answers what its body's materialisation has gathered so far:
            empty until the body has been read.
        """
        if self._source is not None:
            return self._source.uploaded_files()

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
            been parsed into the request. A request built over a connection
            answers what its body's materialisation has yielded so far:
            ``None`` until the body has been read.
        """
        if self._source is not None:
            return self._source.parsed_body()

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
            A fresh mapping of each attribute name to its value. A request
            built over a connection reads them live, off its source: the
            named parameters the matched route fills in are there as soon
            as routing has filled them — which is after the request exists.
        """
        if self._source is not None:
            return self._source.attributes()

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
        if self._source is not None:
            return self._source.attributes().get(name, default)

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
        # Read the copy's bag, not this instance's: a connected request's own
        # is empty, its attributes living on the source the copy detached from.
        new._attributes = {**new._attributes, name: value}  # noqa: SLF001 — a copy of this class.

        return new

    @override
    def without_attribute(self, name: str) -> Self:
        """Return an instance with the ``name`` attribute gone.

        Args:
            name: The attribute name.

        Returns:
            A new instance, or this one when the request carries no such
            attribute. A connected request always answers a copy: its
            attributes are live, so the name is looked for in what they
            answer now, and the copy detaches either way.
        """
        source = self._source
        if source is not None:
            new = self._copy()
            new._attributes = {  # noqa: SLF001 — a copy of this very class.
                held: value for held, value in source.attributes().items() if held != name
            }

            return new

        if name not in self._attributes:
            return self

        new = self._copy()
        new._attributes = {  # noqa: SLF001 — a copy of this very class.
            held: value for held, value in self._attributes.items() if held != name
        }

        return new

    @override
    def _copy(self) -> Self:
        """Return a copy to change, leaving this instance as it is.

        A connected request's copy detaches: it is a plain eager request,
        carrying the head as it was passed and the live parts frozen to
        what they answer at this moment — the attributes as a snapshot,
        the parsed body and the uploaded files as the source's peeks. The
        body is the one lazy stream, shared: one materialisation serves
        the request and every copy of it, and the copy never reads the
        source again.
        """
        source = self._source
        if source is None:
            return super()._copy()

        new = super()._copy()
        new._stream = self.get_body()  # noqa: SLF001 — a copy of this very class.
        new._attributes = dict(source.attributes())  # noqa: SLF001 — a copy of this class.
        new._parsed_body = source.parsed_body()  # noqa: SLF001 — a copy of this class.
        new._uploaded_files = source.uploaded_files()  # noqa: SLF001 — a copy of this class.
        new._source = None  # noqa: SLF001 — a copy of this very class.

        return new
