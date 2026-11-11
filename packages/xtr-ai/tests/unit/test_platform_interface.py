from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic_ai import Agent
from pydantic_ai.capabilities import ResolveModelId
from pydantic_ai.models.test import TestModel
from typing_extensions import override

from xtr_ai import Platform, PlatformInterface, PlatformRegistry, PlatformRegistryInterface

if TYPE_CHECKING:
    from pydantic_ai.models import Model

pytestmark = pytest.mark.anyio


class Gateway(PlatformInterface):
    """A platform of the application's own: models from a client it already holds."""

    def __init__(self) -> None:
        self.closed: bool = False
        self._model: TestModel = TestModel(custom_output_text="through the gateway")

    @property
    @override
    def name(self) -> str:
        return "gateway"

    @property
    @override
    def provider(self) -> str:
        return "gateway"

    @override
    def model(self, model_name: str) -> Model:
        del model_name
        return self._model

    @override
    def built(self, model: object) -> bool:
        return model is self._model

    @override
    async def aclose(self) -> None:
        self.closed = True


def test_the_shipped_classes_are_their_interfaces() -> None:
    assert isinstance(Platform("p", "test"), PlatformInterface)
    assert isinstance(PlatformRegistry.of(), PlatformRegistryInterface)


async def test_a_platform_of_the_applications_own_serves_the_registry() -> None:
    gateway = Gateway()
    registry = PlatformRegistry.of(gateway)
    agent = Agent("gateway:any", capabilities=[ResolveModelId(registry.resolve)])

    result = await agent.run("hi")
    await registry.aclose()

    assert result.output == "through the gateway"
    assert registry.platform_of(gateway.model("any")) == "gateway"
    assert gateway.closed
