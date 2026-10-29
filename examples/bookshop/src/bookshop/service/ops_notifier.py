"""The staff notifier, and the qualified factory that registers it as ``"ops"``."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Target, as_service
from xtr_logging_contracts import LoggerInterface

from bookshop.service.notifier_interface import NotifierInterface

__all__ = ["OpsNotifier", "ops_notifier"]


@final
class OpsNotifier(NotifierInterface):
    """Staff notifications, on the ``security`` channel."""

    def __init__(self, logger: LoggerInterface) -> None:
        """Write to ``logger``."""
        self._logger = logger

    @override
    def notify(self, recipient: str, message: str, /) -> str:
        self._logger.warning(
            "ops {recipient}: {message}", {"recipient": recipient, "message": message}
        )
        return f"paged {recipient}"


@as_service(qualifier="ops")
def ops_notifier(logger: Annotated[LoggerInterface, Target("security")]) -> NotifierInterface:
    """A second ``NotifierInterface``, told apart by the qualifier ``"ops"``.

    Asked for with ``Annotated[NotifierInterface, Target("ops")]`` or
    ``container.get(NotifierInterface, "ops")``.
    """
    return OpsNotifier(logger)
