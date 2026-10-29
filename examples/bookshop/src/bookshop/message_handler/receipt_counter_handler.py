"""A second handler of ``SendReceipt``: every handler of a message runs."""

from __future__ import annotations

from typing import final

from xtr_messenger import as_message_handler

from bookshop.message.send_receipt import SendReceipt

__all__ = ["ReceiptCounter"]


@final
@as_message_handler(SendReceipt)
class ReceiptCounter:
    """A second handler of the same message: every handler runs."""

    def __init__(self) -> None:
        """Count from zero."""
        self.count = 0

    async def __call__(self, message: SendReceipt) -> None:
        """Count one more receipt."""
        del message
        self.count += 1
