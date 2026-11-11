"""Where a named conversation store keeps its conversations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, final

from pydantic_ai.conversation_store import ConversationStore

__all__ = [
    "ConversationStoreEntry",
    "InMemoryConversationStoreConfig",
    "OrmConversationStoreConfig",
    "ServiceConversationStoreConfig",
]


@final
@dataclass(frozen=True, slots=True)
class InMemoryConversationStoreConfig:
    """pydantic-ai's in-memory store: this process only, gone when it stops."""


@final
@dataclass(frozen=True, slots=True)
class OrmConversationStoreConfig:
    """Two tables on an xtr-orm connection; needs ``xtr-ai-orm-conversation-store`` and OrmBundle.

    Attributes:
        connection: The orm connection whose primary keeps the tables.
        table_prefix: What both table names start with.
    """

    connection: str = "default"
    table_prefix: str = "ai_"


@final
@dataclass(frozen=True, slots=True)
class ServiceConversationStoreConfig:
    """A ``ConversationStore`` the application registers itself, under its class."""

    service: type[ConversationStore]


ConversationStoreEntry: TypeAlias = (
    InMemoryConversationStoreConfig | OrmConversationStoreConfig | ServiceConversationStoreConfig
)
"""What ``AiConfig.conversation_stores`` maps a name to."""
