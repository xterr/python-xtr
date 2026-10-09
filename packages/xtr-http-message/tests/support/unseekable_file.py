"""A binary file object whose cursor cannot be moved."""

from __future__ import annotations

import io

from typing_extensions import override

__all__ = ["UnseekableFile"]


class UnseekableFile(io.BytesIO):
    """A buffer over bytes that reports itself as not seekable.

    A real one is a socket or a pipe. This one stands in for either without a
    test needing to open one, and carries its own contract test.
    """

    @override
    def seekable(self) -> bool:
        """Report that the cursor cannot be moved.

        Returns:
            Always ``False``.
        """
        return False
