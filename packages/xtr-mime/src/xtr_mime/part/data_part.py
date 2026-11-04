"""A part carrying a file's bytes: an attachment, an inline image, a form upload."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, BinaryIO, ClassVar

from typing_extensions import override

from xtr_mime.exception import InvalidArgumentError

from .file import File
from .text_part import TextPart

if TYPE_CHECKING:
    from os import PathLike
    from typing import Self

    from xtr_mime.header import Headers

__all__ = ["DataPart"]


class DataPart(TextPart):
    """Bytes with a content type and a filename, attached unless :meth:`as_inline` is called.

    Its content id is made up the first time it is asked for, unless one was set: an HTML
    body refers to an inline image by it, ``cid:<id>``.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_content_id", "_filename", "_media_type")

    def __init__(
        self,
        body: str | bytes | BinaryIO | File,
        filename: str | None = None,
        content_type: str | None = None,
        encoding: str | None = None,
    ) -> None:
        """Keep the body, its filename and its ``type/subtype``.

        A :class:`File` names the part and gives its type unless ``filename`` and
        ``content_type`` say otherwise; anything else is ``application/octet-stream``.

        Raises:
            TypeError: ``body`` is none of the types a body may be.
            InvalidArgumentError: As :class:`TextPart` raises it.
        """
        if isinstance(body, File) and not filename:
            filename = body.get_filename()
        if content_type is None:
            content_type = (
                body.get_content_type() if isinstance(body, File) else "application/octet-stream"
            )
        media_type, _, subtype = content_type.partition("/")
        super().__init__(body, None, subtype, encoding)
        self._media_type: str = media_type
        self._filename: str | None = filename
        self._content_id: str | None = None
        if filename is not None:
            _ = self.set_name(filename)
        _ = self.set_disposition("attachment")

    @staticmethod
    def from_path(
        path: str | PathLike[str],
        name: str | None = None,
        content_type: str | None = None,
        encoding: str | None = None,
    ) -> DataPart:
        """Build a part from a file read when the part is rendered.

        Raises:
            InvalidArgumentError: ``path`` is a directory or a file this process may not
                read, or ``encoding`` is not one the part knows.
        """
        return DataPart(File(path), name, content_type, encoding)

    def as_inline(self) -> Self:
        """Show the part inside the body, not as an attachment."""
        return self.set_disposition("inline")

    def set_content_id(self, content_id: str) -> Self:
        """Set the content id, ``left@right`` without angle brackets.

        Raises:
            InvalidArgumentError: ``content_id`` holds no ``@``.
        """
        if "@" not in content_id:
            raise InvalidArgumentError(
                f'The "{content_id}" CID is invalid as it doesn\'t contain an "@".'
            )
        self._content_id = content_id
        return self

    def get_content_id(self) -> str:
        """Return the content id, made up now if none was set or made up before."""
        if self._content_id is None:
            self._content_id = f"{secrets.token_hex(16)}@xtr"
        return self._content_id

    def has_content_id(self) -> bool:
        """Tell whether a content id was set or made up."""
        return self._content_id is not None

    @override
    def get_media_type(self) -> str:
        """Return the media type of the content type given."""
        return self._media_type

    @override
    def get_prepared_headers(self) -> Headers:
        """Return the text part's headers with the content id and the filename added."""
        headers = super().get_prepared_headers()
        if self._content_id is not None:
            headers.set_header_body("id", "Content-ID", self._content_id)
        if self._filename is not None:
            headers.set_header_parameter("Content-Disposition", "filename", self._filename)
        return headers

    @override
    def as_debug_string(self) -> str:
        """Describe the part: the text part's description and the filename."""
        description = super().as_debug_string()
        if self._filename is not None:
            description += f" filename: {self._filename}"
        return description

    def get_filename(self) -> str | None:
        """Return the filename, ``None`` unless given."""
        return self._filename

    def get_content_type(self) -> str:
        """Return ``type/subtype``."""
        return f"{self.get_media_type()}/{self.get_media_subtype()}"
