"""An uploaded file that satisfies the contract and arrived empty."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.fake_stream import FakeStream
from xtr_http_message_contracts import UploadError

if TYPE_CHECKING:
    from xtr_http_message_contracts import StreamInterface

__all__ = ["FakeUploadedFile"]


class FakeUploadedFile:
    """Answers every question on the uploaded file contract, over an empty file."""

    def get_stream(self) -> StreamInterface:
        return FakeStream()

    def move_to(self, target_path: str) -> None:
        del target_path

    def get_size(self) -> int | None:
        return 0

    def get_error(self) -> int:
        return UploadError.OK

    def get_client_filename(self) -> str | None:
        return None

    def get_client_media_type(self) -> str | None:
        return None
