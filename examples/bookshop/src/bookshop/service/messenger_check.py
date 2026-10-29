"""A startup check placed ``after`` another — see ``startup_check`` for the order."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import as_tagged_item
from xtr_messenger import MessageBusInterface
from xtr_service_contracts import ContainerInterface

from bookshop.service.search_index_check import SearchIndexCheck
from bookshop.service.startup_check import StartupCheck

__all__ = ["MessengerCheck"]


@final
@as_tagged_item(after=[SearchIndexCheck])
class MessengerCheck(StartupCheck):
    """The bus exists — asked through ``ContainerInterface.has``, without building it."""

    def __init__(self, container: ContainerInterface) -> None:
        """Ask ``container``."""
        self._container = container

    @override
    async def run(self) -> str:
        if not self._container.has(MessageBusInterface):
            raise RuntimeError("the messenger bundle is not active")
        return "message bus registered"
