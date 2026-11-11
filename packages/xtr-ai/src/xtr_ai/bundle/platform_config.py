"""One platform's configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, final

from xtr_ai.exception import InvalidConfigurationError

from ._placeholder import is_literal

__all__ = ["PlatformConfig"]


@final
@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """A provider, its key, its endpoint and its other options, under one name.

    Attributes:
        provider: Any provider name pydantic-ai knows (``openai``, ``anthropic``,
            ``azure``, ``bedrock``, ``google``, ``ollama``, …), or ``test`` /
            ``function`` for pydantic-ai's in-process test models.
        api_key: The key, usually ``env("…")``. Never shown in a report.
        base_url: The endpoint, for an OpenAI-compatible server or a proxy.
        options: The provider's other constructor keywords, passed unchanged —
            ``api_version``, ``region``, ``project``, …; for ``test``,
            ``TestModel``'s; for ``function``, ``function`` and/or
            ``stream_function``.
        model_settings: Defaults every model of this platform carries, under
            the agent's and the run's — ``timeout``, ``max_tokens``, …
    """

    provider: str
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    options: Mapping[str, Any] = field(default_factory=dict[str, Any])
    model_settings: Mapping[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Refuse an empty provider name.

        Raises:
            InvalidConfigurationError: When ``provider`` is empty.
        """
        if is_literal(self.provider) and not self.provider:
            raise InvalidConfigurationError("A platform needs a provider.")
