"""Everything the ai bundle is configured with."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import final

from .agent_config import AgentConfig
from .conversation_store_configs import ConversationStoreEntry
from .platform_config import PlatformConfig

__all__ = ["AiConfig"]


@final
@dataclass(frozen=True, slots=True)
class AiConfig:
    """Named platforms, named agents and named conversation stores.

    Empty by default: nothing is registered that is not configured, and
    nothing configured is built before it is first used.

    Attributes:
        platforms: Each platform by name — the prefix of its model ids.
        agents: Each agent by name — what it is injected by.
        conversation_stores: Each conversation store by name; ``"default"`` is
            also injected without a name.
    """

    platforms: Mapping[str, PlatformConfig] = field(default_factory=dict[str, PlatformConfig])
    agents: Mapping[str, AgentConfig] = field(default_factory=dict[str, AgentConfig])
    conversation_stores: Mapping[str, ConversationStoreEntry] = field(
        default_factory=dict[str, ConversationStoreEntry]
    )
