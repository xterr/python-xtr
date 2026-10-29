"""A service that exists only while its peers do: ``@remove_if_missing``, repeated."""

from __future__ import annotations

from typing import Annotated, final

from xtr_dependency_injection import Target, as_service, remove_if_missing
from xtr_logging_contracts import LoggerInterface

__all__ = ["SecurityAuditTrail"]


@final
@remove_if_missing(service=LoggerInterface, qualifier="security")
@remove_if_missing(package="xtr-logging")
@as_service
class SecurityAuditTrail:
    """Writes the audit trail to the ``security`` channel.

    Each ``@remove_if_missing`` is a condition, and every one must hold for the service to
    survive the ``RemoveMissingDependenciesPass``:

    - ``service=LoggerInterface, qualifier="security"`` — the ``security`` channel's logger
      exists (the logging bundle is active and declares the channel);
    - ``package="xtr-logging"`` — that distribution is installed.

    Dropped otherwise, together with every alias of it — a decorator of it would follow its
    ``on_invalid``.
    """

    def __init__(self, logger: Annotated[LoggerInterface, Target("security")]) -> None:
        """Write to the ``security`` channel's logger."""
        self._logger = logger

    def record(self, subject: str, detail: str) -> None:
        """Write one audit entry."""
        self._logger.notice("{subject}: {detail}", {"subject": subject, "detail": detail})
