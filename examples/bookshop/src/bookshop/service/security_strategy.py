"""The activation strategy the logging config names by id — see ``memory_handler``."""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_logging import ActivationStrategyInterface, ChannelLevelActivationStrategy

__all__ = ["security_strategy"]


@as_service(qualifier="security")
def security_strategy() -> ActivationStrategyInterface:
    """Trigger a fingers-crossed flush at WARNING on ``security``, at ERROR elsewhere."""
    return ChannelLevelActivationStrategy("error", {"security": "warning"})
