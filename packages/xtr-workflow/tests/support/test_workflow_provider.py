"""The workflow provider keeps its own contract: it provides each workflow it holds, by name."""

from __future__ import annotations

import pytest
from xtr_service_contracts import ServiceProviderInterface

from tests.support.workflow_provider import WorkflowProvider
from tests.support.workflow_stub import WorkflowStub
from xtr_workflow import WorkflowInterface


def test_it_is_a_service_provider_naming_its_workflows() -> None:
    provider = WorkflowProvider({"article": WorkflowStub()})

    assert isinstance(provider, ServiceProviderInterface)
    assert provider.has("article")
    assert not provider.has("pull_request")
    assert dict(provider.provided_services()) == {"article": WorkflowInterface}


@pytest.mark.anyio
async def test_it_hands_out_the_workflow_named() -> None:
    workflow = WorkflowStub()
    provider = WorkflowProvider({"article": workflow})

    assert await provider.get("article") is workflow


@pytest.mark.anyio
async def test_it_refuses_a_name_it_does_not_provide() -> None:
    provider = WorkflowProvider({})

    with pytest.raises(LookupError):
        _ = await provider.get("article")
