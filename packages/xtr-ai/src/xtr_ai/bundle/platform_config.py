"""One platform's configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Final, final, override

from xtr_ai.exception import InvalidConfigurationError

from ._placeholder import is_literal

__all__ = ["PlatformConfig"]

_USERINFO: Final = re.compile(r"(?<=://)[^/@\s]+(?=@)")
"""The credentials a URL may carry before its host."""

_HIDDEN: Final = "[hidden]"


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

    Its ``repr`` names every option but shows none of their values, and masks
    the credentials a ``base_url`` carries: an option can hold a key under any
    name a provider gives it.
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

    @override
    def __repr__(self) -> str:
        """Show the platform without the key, any option's value, or the URL's credentials."""
        base_url = (
            _USERINFO.sub(_HIDDEN, self.base_url)
            if isinstance(self.base_url, str)
            else self.base_url
        )
        options = dict.fromkeys(self.options, _HIDDEN)
        return (
            f"PlatformConfig(provider={self.provider!r}, base_url={base_url!r}, "
            f"options={options!r}, model_settings={dict(self.model_settings)!r})"
        )
