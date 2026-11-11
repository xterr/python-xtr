"""Every error this library raises.

All of them derive from :class:`AiError`, so one ``except`` catches anything
the integration can go wrong with. pydantic-ai's own errors — a model that
failed, a run that was cancelled — are raised as pydantic-ai raises them.
"""

from __future__ import annotations

from .ai_error import AiError
from .invalid_configuration_error import InvalidConfigurationError
from .platform_unavailable_error import PlatformUnavailableError
from .run_in_progress_error import RunInProgressError
from .unknown_run_error import UnknownRunError

__all__ = [
    "AiError",
    "InvalidConfigurationError",
    "PlatformUnavailableError",
    "RunInProgressError",
    "UnknownRunError",
]
