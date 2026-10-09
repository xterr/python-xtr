"""One factory for every kind of message, so a caller need name no class."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_http_message_contracts import UploadError
from xtr_http_message_contracts.factory import (
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
)

from xtr_http_message.exception import InvalidArgumentError, StreamError
from xtr_http_message.request import Request
from xtr_http_message.response import Response
from xtr_http_message.server_request import ServerRequest
from xtr_http_message.stream import Stream
from xtr_http_message.uploaded_file import UploadedFile
from xtr_http_message.uri import Uri

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import BinaryIO

    from xtr_http_message_contracts import (
        RequestInterface,
        ResponseInterface,
        ServerRequestInterface,
        StreamInterface,
        UploadedFileInterface,
        UriInterface,
    )

__all__ = ["HttpFactory"]


@final
class HttpFactory(
    RequestFactoryInterface,
    ResponseFactoryInterface,
    ServerRequestFactoryInterface,
    StreamFactoryInterface,
    UploadedFileFactoryInterface,
    UriFactoryInterface,
):
    """Builds every kind of message this package implements.

    One object rather than six, because the six belong together: a library
    given this one can build whatever it needs, and an application that wants
    to swap the implementation out swaps one registration.

    ```python
    from xtr_http_message.factory import HttpFactory

    factory = HttpFactory()
    response = factory.create_response(404)
    assert response.get_reason_phrase() == "Not Found"
    ```

    It holds no state, so one instance serves a whole application.
    """

    __slots__ = ()

    @override
    def create_request(self, method: str, uri: UriInterface | str) -> RequestInterface:
        """Return a new request for ``method`` and ``uri``.

        Args:
            method: The HTTP method of the request.
            uri: The URI of the request. Given as text, it is read into one.

        Returns:
            The request.
        """
        return Request(method, uri)

    @override
    def create_response(
        self,
        code: int = 200,
        reason_phrase: str | None = None,
    ) -> ResponseInterface:
        """Return a new response for ``code``.

        Args:
            code: The status code.
            reason_phrase: The phrase to go with ``code``. Left out, the
                recommended phrase for the code is filled in where there is
                one; given as an empty string, the response carries no phrase
                at all. That is the difference between asking for the usual
                phrase and asking for none.

        Returns:
            The response.
        """
        return Response(code, None, None, "1.1", reason_phrase)

    @override
    def create_server_request(
        self,
        method: str,
        uri: UriInterface | str,
        server_params: Mapping[str, object] | None = None,
    ) -> ServerRequestInterface:
        """Return a new server request for ``method`` and ``uri``.

        The environment parameters are taken exactly as given: nothing in them
        is read, and in particular neither the method nor the URI, which is
        why both have to be passed.

        Args:
            method: The HTTP method of the request.
            uri: The URI of the request. Given as text, it is read into one.
            server_params: The environment parameters to seed the request
                with. ``None`` seeds it with none.

        Returns:
            The server request.
        """
        return ServerRequest(method, uri, None, None, "1.1", server_params)

    @override
    def create_stream(self, content: bytes = b"") -> StreamInterface:
        """Return a new stream over ``content``, held in memory.

        Args:
            content: The bytes the stream reads back.

        Returns:
            The stream, with its cursor at the first byte.
        """
        return Stream.create(content)

    @override
    def create_stream_from_file(self, filename: str, mode: str = "r") -> StreamInterface:
        """Return a new stream over the file at ``filename``.

        Args:
            filename: The path to open.
            mode: How to open it. The payload is bytes, so the mode is taken
                as a binary one whether or not it says so.

        Returns:
            The stream.

        Raises:
            InvalidArgumentError: When the mode is not a mode.
            StreamError: When the path is empty, or the file cannot be opened.
        """
        if filename == "":
            raise StreamError("Path cannot be empty")

        binary = mode if "b" in mode else f"{mode}b"

        try:
            # The stream takes the file over and closes it, so there is no
            # context manager here to close it first (SIM115). The mode is
            # binary by the line above, which a mode computed at run time
            # cannot say in a type.
            opened = Path(filename).open(binary)  # noqa: SIM115
        except ValueError as invalid:
            # Not a mode at all, which is worth telling apart from a file that
            # will not open.
            message = f'The mode "{mode}" is invalid.'
            raise InvalidArgumentError(message) from invalid
        except OSError as failure:
            message = f'The file "{filename}" cannot be opened: {failure}'
            raise StreamError(message) from failure

        return Stream.create(cast("BinaryIO", opened))

    @override
    def create_stream_from_resource(self, resource: BinaryIO) -> StreamInterface:
        """Return a new stream over an open binary file object.

        Args:
            resource: The file object. The stream takes it over: closing the
                stream closes it.

        Returns:
            The stream.
        """
        return Stream.create(resource)

    @override
    def create_uploaded_file(
        self,
        stream: StreamInterface,
        size: int | None = None,
        error: int = UploadError.OK,
        client_filename: str | None = None,
        client_media_type: str | None = None,
    ) -> UploadedFileInterface:
        """Return a new uploaded file reading from ``stream``.

        Args:
            stream: The contents of the uploaded file.
            size: The size in bytes. Left out, it is read off the stream.
            error: How the upload went.
            client_filename: The file name the client sent, if any.
            client_media_type: The media type the client sent, if any.

        Returns:
            The uploaded file.

        Raises:
            InvalidArgumentError: When ``error`` is not one of the upload
                outcomes.
        """
        if size is None:
            size = stream.get_size()

        return UploadedFile(stream, size, error, client_filename, client_media_type)

    @override
    def create_uri(self, uri: str = "") -> UriInterface:
        """Return a new URI read from ``uri``.

        Args:
            uri: The URI as text. Empty builds one with no component at all.

        Returns:
            The URI.

        Raises:
            InvalidArgumentError: When the text cannot be read as a URI.
        """
        return Uri(uri)
