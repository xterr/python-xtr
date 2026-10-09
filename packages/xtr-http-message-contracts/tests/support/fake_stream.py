"""A stream that satisfies the contract and carries nothing."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import BinaryIO

__all__ = ["FakeStream"]


class FakeStream:
    """Answers every question on the stream contract, over an empty body.

    Nothing here does any work: these tests ask whether the contract is
    satisfied, not whether a stream behaves.
    """

    def __bytes__(self) -> bytes:
        return b""

    def close(self) -> None: ...

    def detach(self) -> BinaryIO | None:
        return None

    def get_size(self) -> int | None:
        return 0

    def tell(self) -> int:
        return 0

    def eof(self) -> bool:
        return True

    def is_seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> None:
        del offset, whence

    def rewind(self) -> None: ...

    def is_writable(self) -> bool:
        return True

    def write(self, data: bytes) -> int:
        return len(data)

    def is_readable(self) -> bool:
        return True

    def read(self, length: int) -> bytes:
        del length
        return b""

    def get_contents(self) -> bytes:
        return b""

    def get_metadata(self, key: str | None = None) -> object:
        del key
        return None
