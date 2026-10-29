"""The notifier outside prod: ``@when_not("prod")`` and ``@as_alias`` of the interface."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Target, as_alias, as_service, when_not
from xtr_logging_contracts import LoggerInterface

from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["LogNotifier"]


@final
@when_not("prod")
@as_alias(NotifierInterface)
@as_service
class LogNotifier(NotifierInterface):
    """Outside prod, a notification is a log record on the ``orders`` channel."""

    def __init__(self, logger: Annotated[LoggerInterface, Target("orders")]) -> None:
        """Write to ``logger``."""
        self._logger = logger

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        self._logger.notice(
            "to {recipient}: {message}", {"recipient": recipient, "message": message}
        )
        return f"logged for {recipient}"
