"""An orm conversation store, with the orm bundle left out."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_ai.bundle import AiConfig, OrmConversationStoreConfig


@configure
def ai() -> AiConfig:
    return AiConfig(conversation_stores={"default": OrmConversationStoreConfig()})
