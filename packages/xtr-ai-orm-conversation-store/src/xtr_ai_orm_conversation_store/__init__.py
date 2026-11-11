"""Agent conversations stored in a relational database, for xtr-ai.

:class:`OrmConversationStore` is a pydantic-ai ``ConversationStore`` on two
tables, written through an xtr-orm connection's engine in short transactions of
its own. :class:`ConversationMappingDriver` adds those tables to a connection's
definitions, so ``orm:migrations:diff`` writes them.
"""

from __future__ import annotations

from .conversation_mapping_driver import ConversationMappingDriver
from .conversation_tables import DEFAULT_TABLE_PREFIX, ConversationTables
from .orm_conversation_store import OrmConversationStore

__all__ = [
    "DEFAULT_TABLE_PREFIX",
    "ConversationMappingDriver",
    "ConversationTables",
    "OrmConversationStore",
]
