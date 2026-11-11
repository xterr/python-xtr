"""The container integration: one bundle, configured by :class:`AiConfig`."""

from __future__ import annotations

from ._agent_factories import AI_CHANNEL
from ._tool_wiring import TOOL_TAG
from .agent_config import AgentConfig, CapabilityEntry
from .ai_bundle import DEFAULT_STORE, AiBundle
from .ai_config import AiConfig
from .conversation_store_configs import (
    ConversationStoreEntry,
    InMemoryConversationStoreConfig,
    OrmConversationStoreConfig,
    ServiceConversationStoreConfig,
)
from .model_ref import ModelRef
from .platform_config import PlatformConfig
from .toolset_configs import AgentToolRef, ToolsetEntry, ToolsetRef

__all__ = [
    "AI_CHANNEL",
    "DEFAULT_STORE",
    "TOOL_TAG",
    "AgentConfig",
    "AgentToolRef",
    "AiBundle",
    "AiConfig",
    "CapabilityEntry",
    "ConversationStoreEntry",
    "InMemoryConversationStoreConfig",
    "ModelRef",
    "OrmConversationStoreConfig",
    "PlatformConfig",
    "ServiceConversationStoreConfig",
    "ToolsetEntry",
    "ToolsetRef",
]
