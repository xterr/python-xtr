from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_http_kernel.profiler import Profiler

from tests.support.serving import application, serving
from xtr_web_profiler.bundle import WebProfilerBundle

pytestmark = pytest.mark.anyio


async def test_the_bundle_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(WebProfilerBundle)


async def test_listing_the_bundle_turns_profiling_on() -> None:
    kernel = Kernel(
        "xtr_web_profiler.bundle",
        env="dev",
        bundles={WebProfilerBundle: {"all": True}},
        resources=(),
    )

    async with await kernel.boot() as booted:
        assert booted.container.has(Profiler)


def test_the_bundle_warns_when_active_in_production() -> None:
    with pytest.warns(UserWarning, match="active in the prod environment"):
        _ = application(env="prod")


async def test_serving_in_production_still_works() -> None:
    with pytest.warns(UserWarning, match="prod"):
        app = application(env="prod")
    async with serving(app) as client:
        response = await client.get("/data")

    assert response.status_code == 200
