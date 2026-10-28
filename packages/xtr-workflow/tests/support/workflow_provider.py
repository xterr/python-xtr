"""Workflows by name behind the service provider contract, as a container's locator offers them."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ServiceProviderInterface

from xtr_workflow import WorkflowInterface

if TYPE_CHECKING:
    from collections.abc import Hashable, Mapping

__all__ = ["WorkflowProvider"]


@final
class WorkflowProvider(ServiceProviderInterface[WorkflowInterface]):
    """Hands out the workflows it holds, by name."""

    def __init__(self, workflows: Mapping[str, WorkflowInterface]) -> None:
        self._workflows = dict(workflows)

    @override
    async def get(self, name: Hashable, /) -> WorkflowInterface:
        return self._workflows[str(name)]

    @override
    def has(self, name: Hashable, /) -> bool:
        return name in self._workflows

    @override
    def provided_services(self) -> Mapping[Hashable, type[object]]:
        return MappingProxyType(dict.fromkeys(self._workflows, WorkflowInterface))
