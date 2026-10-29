"""The handler of ``StockAlert``: a function handler asking for a qualified service."""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Target
from xtr_messenger import as_message_handler

from bookshop.message.stock_alert import StockAlert
from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["page_purchasing"]


@as_message_handler(StockAlert)
async def page_purchasing(
    message: StockAlert,
    notifier: Annotated[NotifierInterface, Target("ops")],
) -> None:
    """Page purchasing through the qualified — and decorated — ``"ops"`` notifier."""
    _ = notifier.notify("purchasing", f"{message.isbn} sold {message.ordered} at once")
