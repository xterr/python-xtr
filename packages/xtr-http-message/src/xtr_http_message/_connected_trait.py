"""The connected side of a server request: born over a source, read through it.

A request that arrived is not always known in full when it becomes a
message — a connection hands over its head at once, but its body is
still on the wire. This is the plumbing that lets the one server request
class be born that way, connected to a source that answers the body side
late, while the eager path the class has always had stays exactly as it
was. A mixin, for the same reason the message's own traits are: this is
one part of what a server request answers, and the class composing it
carries the rest.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Self

from typing_extensions import override

from ._request_trait import RequestTrait
from .lazy_stream import LazyStream

if TYPE_CHECKING:
    from xtr_http_message_contracts import StreamInterface, UriInterface

    from .request_source import RequestSource

__all__ = ["ConnectedTrait"]


class ConnectedTrait(RequestTrait):
    """The body side of a server request that arrives late, over a source.

    The ``with_*`` members a connected request answers detach: the copy
    is a plain eager request — the live parts frozen to what they answer
    at that moment — so a change a listener makes never reaches the
    connection. Because the copy is the same class, the ``Self`` the
    ``with_*`` members promise is finally the whole truth.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_source",)

    def __init__(self) -> None:
        """Start connected to nothing; :meth:`ServerRequest.over` connects."""
        super().__init__()
        self._source: RequestSource | None = None

    @override
    def get_body(self) -> StreamInterface:
        """Return the body of the message.

        A connected request's body is one lazy stream over its source,
        handed out however many times the body is asked for: the first
        read materialises the whole body once, and every later read is
        served out of the buffer.

        Returns:
            The body, as a stream.
        """
        if self._source is not None and self._stream is None:
            self._stream: StreamInterface | None = LazyStream(self._source.materialise)

        return super().get_body()

    async def ensure_parsed(self) -> None:
        """Materialise the body side, when connected and nothing has read it yet.

        The seam that can still await calls this before the message is
        handed on: a consumer written against the contract reads
        :meth:`~xtr_http_message.server_request.ServerRequest.get_parsed_body`
        without reading the stream first, and only a body that has been
        read can answer it. A no-op for an eager request, and for one
        whose body has already been read.
        """
        if self._source is None:
            return

        body = self.get_body()
        if isinstance(body, LazyStream) and not body.materialised:
            _ = await body.get_contents()

    @override
    def with_protocol_version(self, version: str) -> Self:
        """Return an instance carrying ``version``; a connected one detaches first."""
        if self._source is not None:
            return self._copy().with_protocol_version(version)

        return super().with_protocol_version(version)

    @override
    def without_header(self, name: str) -> Self:
        """Return an instance with the ``name`` header gone; a connected one detaches first."""
        if self._source is not None:
            return self._copy().without_header(name)

        return super().without_header(name)

    @override
    def with_body(self, body: StreamInterface) -> Self:
        """Return an instance reading its body from ``body``; a connected one detaches first."""
        if self._source is not None:
            return self._copy().with_body(body)

        return super().with_body(body)

    @override
    def with_uri(self, uri: UriInterface, preserve_host: bool = False) -> Self:
        """Return an instance for ``uri``; a connected one detaches first.

        The copy is a plain eager request, so the URI it carries is a
        value, not a view — and a ``Host`` header is kept where asked.
        """
        if self._source is not None:
            return self._copy().with_uri(uri, preserve_host)

        return super().with_uri(uri, preserve_host)
