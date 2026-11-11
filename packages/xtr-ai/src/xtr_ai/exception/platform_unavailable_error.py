"""A platform that cannot be built where a run needs it."""

from __future__ import annotations

from typing import final

from .ai_error import AiError

__all__ = ["PlatformUnavailableError"]


@final
class PlatformUnavailableError(AiError):
    """A platform that is not configured, or cannot be built.

    Raised the first time a run needs the platform — never while the container
    builds — so the console runs without any key. The message names the platform
    and, where one is missing, the environment variable or the package extra;
    it never carries a secret's value.

    Attributes:
        platform: The platform asked for.
        reason: Why it cannot be used.
    """

    platform: str
    reason: str

    def __init__(self, platform: str, reason: str) -> None:
        """Name the platform and why it cannot be used."""
        self.platform = platform
        self.reason = reason
        super().__init__(f'The "{platform}" platform is unavailable: {reason}')
