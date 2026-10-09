"""A binary file object that can be written to but not read from."""

from __future__ import annotations

import io

from typing_extensions import override

__all__ = ["UnreadableFile"]


class UnreadableFile(io.BytesIO):
    """A buffer over bytes that reports itself as write-only.

    A real one is the write end of a pipe or a socket opened to send. This one
    stands in for either, and carries its own contract test.
    """

    @override
    def readable(self) -> bool:
        """Report that nothing can be read back.

        Returns:
            Always ``False``.
        """
        return False
