"""A conversation store and run control the application registers itself."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic_ai.conversation_store import InMemoryConversationStore
from xtr_dependency_injection import as_service, configure

from xtr_ai import InMemoryRunControl
from xtr_ai.bundle import AiConfig, ServiceConversationStoreConfig, ServiceRunControlConfig

if TYPE_CHECKING:
    from collections.abc import Mapping
    from contextlib import AbstractAsyncContextManager

    from pydantic_ai import CancellationToken

    from xtr_ai import RunStatus, WatchedRun


@as_service
class ArchiveStore(InMemoryConversationStore):
    """The application's own store."""


@as_service
class OwnRunControl:
    """The application's own run control, delegating to an in-memory one."""

    def __init__(self) -> None:
        self.inner: InMemoryRunControl = InMemoryRunControl()

    async def start(
        self,
        run_id: str,
        *,
        agent: str,
        conversation_id: str | None = None,
        parent_run_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RunStatus:
        return await self.inner.start(
            run_id,
            agent=agent,
            conversation_id=conversation_id,
            parent_run_id=parent_run_id,
            metadata=metadata,
        )

    def watch(
        self, run_id: str, token: CancellationToken
    ) -> AbstractAsyncContextManager[WatchedRun]:
        return self.inner.watch(run_id, token)

    async def get(self, run_id: str) -> RunStatus | None:
        return await self.inner.get(run_id)

    async def request_cancel(self, run_id: str) -> bool:
        return await self.inner.request_cancel(run_id)


@configure
def ai() -> AiConfig:
    return AiConfig(
        conversation_stores={"archive": ServiceConversationStoreConfig(service=ArchiveStore)},
        runs=ServiceRunControlConfig(service=OwnRunControl),
    )
