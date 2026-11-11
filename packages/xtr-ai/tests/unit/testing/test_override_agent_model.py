from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel
from xtr_dependency_injection import Kernel

from xtr_ai.testing import override_agent_model

pytestmark = pytest.mark.anyio


async def test_the_agent_runs_on_the_scripted_model_inside_the_block_only() -> None:
    async with await Kernel("tests.fixtures.app_ai", env="test").boot() as booted:
        async with override_agent_model(
            booted.container, "research", TestModel(custom_output_text="scripted")
        ) as agent:
            inside = await agent.run("hi")
        outside = await agent.run("hi")

    assert inside.output == "scripted"
    assert outside.output == "offline answer"
