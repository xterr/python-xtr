"""A configuration that cannot be used as written."""

from __future__ import annotations

from typing import final

from .ai_error import AiError

__all__ = ["InvalidConfigurationError"]


@final
class InvalidConfigurationError(AiError, ValueError):
    """A platform, agent, store or run-control configuration that cannot be used.

    Raised while the container builds, or when a class is built by hand with a
    value it cannot use. The message names the entry at fault.
    """
