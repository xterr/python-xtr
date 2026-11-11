"""The factories of the conversation stores and of run control."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Final

from pydantic_ai.conversation_store import ConversationStore, InMemoryConversationStore
from xtr_clock import ClockInterface
from xtr_dependency_injection import Target, named_factory

from xtr_ai.in_memory_run_control import InMemoryRunControl
from xtr_ai.run_control_interface import RunControlInterface

from .conversation_store_configs import (
    ConversationStoreEntry,
    InMemoryConversationStoreConfig,
    OrmConversationStoreConfig,
)
from .run_control_configs import InMemoryRunControlConfig, OrmRunControlConfig, RunControlEntry

__all__ = [
    "CONVERSATION_STORE_BRIDGE",
    "RUN_CONTROL_BRIDGE",
    "conversation_store_factory",
    "run_control_factory",
]

CONVERSATION_STORE_BRIDGE: Final = "xtr_ai_orm_conversation_store"
"""The package an orm conversation store needs."""

RUN_CONTROL_BRIDGE: Final = "xtr_ai_orm_run_control"
"""The package orm run control needs."""


def conversation_store_factory(name: str, entry: ConversationStoreEntry) -> Callable[..., object]:
    """Build the factory of the conversation store ``name``.

    An orm store imports its bridge here, which the bundle only reaches once
    it checked the bridge is installed.
    """
    if isinstance(entry, InMemoryConversationStoreConfig):

        def in_memory() -> ConversationStore:
            return InMemoryConversationStore()

        in_memory.__annotations__ = {"return": ConversationStore}
        return named_factory(in_memory, f"ai_conversation_store_{name}")
    if isinstance(entry, OrmConversationStoreConfig):
        # The orm and the bridge are optional; the bundle checked the bridge is installed.
        from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: PLC0415
        from xtr_ai_orm_conversation_store import OrmConversationStore  # noqa: PLC0415

        table_prefix = entry.table_prefix

        def orm(engine: Any) -> ConversationStore:
            return OrmConversationStore(engine, table_prefix=table_prefix)

        orm.__annotations__ = {
            "engine": Annotated[AsyncEngine, Target(entry.connection)],
            "return": ConversationStore,
        }
        return named_factory(orm, f"ai_conversation_store_{name}")

    def service(registered: Any) -> ConversationStore:
        return registered

    service.__annotations__ = {"registered": entry.service, "return": ConversationStore}
    return named_factory(service, f"ai_conversation_store_{name}")


def run_control_factory(entry: RunControlEntry) -> Callable[..., object]:
    """Build the factory of run control; the bundle gives ``clock`` as ``None`` without a clock."""
    if isinstance(entry, InMemoryRunControlConfig):

        def in_memory(clock: ClockInterface | None = None) -> RunControlInterface:
            return InMemoryRunControl(
                clock=clock,
                cancel_poll_interval=entry.cancel_poll_interval,
                heartbeat_interval=entry.heartbeat_interval,
                stale_after=entry.stale_after,
            )

        in_memory.__annotations__ = {"clock": ClockInterface, "return": RunControlInterface}
        return named_factory(in_memory, "ai_run_control")
    if isinstance(entry, OrmRunControlConfig):
        # The orm and the bridge are optional; the bundle checked the bridge is installed.
        from sqlalchemy.ext.asyncio import AsyncEngine  # noqa: PLC0415
        from xtr_ai_orm_run_control import OrmRunControl  # noqa: PLC0415

        def orm(engine: Any, clock: ClockInterface | None = None) -> RunControlInterface:
            return OrmRunControl(
                engine,
                table_prefix=entry.table_prefix,
                clock=clock,
                cancel_poll_interval=entry.cancel_poll_interval,
                heartbeat_interval=entry.heartbeat_interval,
                stale_after=entry.stale_after,
            )

        orm.__annotations__ = {
            "engine": Annotated[AsyncEngine, Target(entry.connection)],
            "clock": ClockInterface,
            "return": RunControlInterface,
        }
        return named_factory(orm, "ai_run_control")

    def service(registered: Any) -> RunControlInterface:
        return registered

    service.__annotations__ = {"registered": entry.service, "return": RunControlInterface}
    return named_factory(service, "ai_run_control")
