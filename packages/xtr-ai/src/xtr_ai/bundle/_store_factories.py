"""The factory of each conversation store."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Final, assert_never

from pydantic_ai.conversation_store import ConversationStore, InMemoryConversationStore
from xtr_dependency_injection import Target, named_factory

from .conversation_store_configs import (
    ConversationStoreEntry,
    InMemoryConversationStoreConfig,
    OrmConversationStoreConfig,
    ServiceConversationStoreConfig,
)

__all__ = ["CONVERSATION_STORE_BRIDGE", "conversation_store_factory"]

CONVERSATION_STORE_BRIDGE: Final = "xtr_ai_orm_conversation_store"
"""The package an orm conversation store needs."""


def conversation_store_factory(name: str, entry: ConversationStoreEntry) -> Callable[..., object]:
    """Build the factory of the conversation store ``name``.

    An orm store imports its bridge here, which the bundle only reaches once
    it checked the bridge is installed. A store configuration added to the
    union without a case here fails the type check, at ``assert_never``.
    """
    factory_name = f"ai_conversation_store_{name}"
    match entry:
        case InMemoryConversationStoreConfig():

            def in_memory() -> ConversationStore:
                return InMemoryConversationStore()

            in_memory.__annotations__ = {"return": ConversationStore}
            return named_factory(in_memory, factory_name)
        case OrmConversationStoreConfig(connection=connection, table_prefix=table_prefix):
            # The orm and the bridge are optional; the bundle checked the bridge is installed.
            from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: PLC0415
            from xtr_ai_orm_conversation_store import OrmConversationStore  # noqa: PLC0415

            def orm(engine: Any) -> ConversationStore:
                return OrmConversationStore(engine, table_prefix=table_prefix)

            orm.__annotations__ = {
                "engine": Annotated[AsyncEngine, Target(connection)],
                "return": ConversationStore,
            }
            return named_factory(orm, factory_name)
        case ServiceConversationStoreConfig(service=registered_type):

            def service(registered: Any) -> ConversationStore:
                return registered

            service.__annotations__ = {"registered": registered_type, "return": ConversationStore}
            return named_factory(service, factory_name)
        case _:
            assert_never(entry)
