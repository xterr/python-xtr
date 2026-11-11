"""Conversations on the default connection."""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure, env
from xtr_orm.bundle import ConnectionConfig, OrmConfig

from xtr_ai.bundle import AiConfig, OrmConversationStoreConfig

BIND_KEY: Final = "xtr_ai_test_app"
"""Where this application's table definitions live; its own, so no other test's join them."""

URL_VARIABLE: Final = "AI_TEST_DATABASE_URL"


@configure
def ai() -> AiConfig:
    return AiConfig(conversation_stores={"default": OrmConversationStoreConfig()})


@configure
def orm() -> OrmConfig:
    return OrmConfig(
        connections={"default": ConnectionConfig(url=env(URL_VARIABLE), bind_key=BIND_KEY)}
    )
