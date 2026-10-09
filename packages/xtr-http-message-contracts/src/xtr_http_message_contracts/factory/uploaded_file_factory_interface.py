"""Build an uploaded file."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from xtr_http_message_contracts.upload_error import UploadError

if TYPE_CHECKING:
    from xtr_http_message_contracts.stream_interface import StreamInterface
    from xtr_http_message_contracts.uploaded_file_interface import UploadedFileInterface

__all__ = ["UploadedFileFactoryInterface"]


@runtime_checkable
class UploadedFileFactoryInterface(Protocol):
    """Makes an uploaded file, so that a caller need not name the class that is one."""

    def create_uploaded_file(
        self,
        stream: StreamInterface,
        size: int | None = None,
        error: int = UploadError.OK,
        client_filename: str | None = None,
        client_media_type: str | None = None,
    ) -> UploadedFileInterface:
        """Return a new uploaded file reading from ``stream``.

        Given no size, the factory works it out from the stream itself.

        Args:
            stream: The contents of the uploaded file.
            size: The size in bytes, when it is already known.
            error: How the upload went, as one of
                :class:`~xtr_http_message_contracts.upload_error.UploadError`.
            client_filename: The file name the client sent, if any.
            client_media_type: The media type the client sent, if any.

        Returns:
            The uploaded file.

        Raises:
            ValueError: When the stream cannot be read.
        """
        ...
