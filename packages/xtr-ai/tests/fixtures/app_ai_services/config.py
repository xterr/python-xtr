"""A conversation store the application registers itself."""

from __future__ import annotations

from pydantic_ai.conversation_store import InMemoryConversationStore
from xtr_dependency_injection import as_service, configure

from xtr_ai.bundle import AiConfig, ServiceConversationStoreConfig


@as_service
class ArchiveStore(InMemoryConversationStore):
    """The application's own store."""


@configure
def ai() -> AiConfig:
    return AiConfig(
        conversation_stores={"archive": ServiceConversationStoreConfig(service=ArchiveStore)},
    )
