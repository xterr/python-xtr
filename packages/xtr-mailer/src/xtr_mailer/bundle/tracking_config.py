"""Whether a provider tracks the opens and clicks of every email."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

__all__ = ["TrackingConfig"]


@final
@dataclass(frozen=True, slots=True)
class TrackingConfig:
    """Asks the provider to track opens and clicks, or not, through an ``X-Track`` header.

    Buildable with no arguments: then each provider keeps its own default. An ``X-Track``
    header among the configured headers wins over these, and one set on an email wins over
    both.

    Attributes:
        opens: Whether opens are tracked; ``None`` keeps the provider's default.
        clicks: Whether clicks are tracked; ``None`` keeps the provider's default.
    """

    opens: bool | None = None
    clicks: bool | None = None

    def is_configured(self) -> bool:
        """Tell whether every email asks for tracking one way or the other."""
        return self.opens is not None or self.clicks is not None
