"""A draft: an email a mail client opens, finishes and sends itself."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from typing_extensions import override

from .email import Email

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from .header import Headers
    from .part import AbstractPart

__all__ = ["DraftEmail"]


class DraftEmail(Email):
    """An email marked ``X-Unsent: 1``, which a mail client opens as a draft to send.

    It needs no author, date or identifier — the client that sends it adds them — so its
    prepared headers add only ``MIME-Version``. Being a draft, it is never valid to send.
    """

    def __init__(
        self,
        headers: Headers | None = None,
        body: AbstractPart | None = None,
        *,
        clock: ClockInterface | None = None,
    ) -> None:
        """Start as an email does, marked as unsent."""
        super().__init__(headers, body, clock=clock)
        _ = self.get_headers().add_text_header("X-Unsent", "1")

    @override
    def get_prepared_headers(self) -> Headers:
        """Return a copy of the headers with ``MIME-Version`` added and ``Bcc`` taken out."""
        headers = copy.copy(self.get_headers())
        if not headers.has("MIME-Version"):
            _ = headers.add_text_header("MIME-Version", "1.0")
        headers.remove("Bcc")
        return headers
