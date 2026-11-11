from __future__ import annotations

from sqlalchemy import MetaData

from xtr_ai_orm_conversation_store import ConversationMappingDriver


def test_the_tables_are_added_once() -> None:
    metadata = MetaData()
    driver = ConversationMappingDriver()

    assert driver.load_metadata(metadata) == ("ai_conversation", "ai_conversation_entry")
    assert driver.load_metadata(metadata) == ()


def test_the_prefix_names_the_tables() -> None:
    metadata = MetaData()

    assert ConversationMappingDriver("chat_").load_metadata(metadata) == (
        "chat_conversation",
        "chat_conversation_entry",
    )
