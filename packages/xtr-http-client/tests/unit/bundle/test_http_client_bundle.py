from __future__ import annotations

import sys

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import assert_zero_config
from xtr_http_client_contracts import HttpClientInterface

from xtr_http_client import HttpxHttpClient, MockHttpClient
from xtr_http_client.bundle import HttpClientBundle
from xtr_http_client.exception import InvalidArgumentError

pytestmark = pytest.mark.anyio

_UNPACED_APP = "tests.fixtures.app_http_client_unpaced"


def _bundle_alone() -> Kernel:
    return Kernel(
        HttpClientBundle.__module__,
        env="test",
        bundles={HttpClientBundle: {"all": True}},
        resources=(),
    )


async def test_it_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(HttpClientBundle)


async def test_with_no_configuration_the_client_is_the_real_transport_alone() -> None:
    async with await _bundle_alone().boot() as booted:
        client = await booted.container.get(HttpClientInterface)

        assert client is await booted.container.get(HttpxHttpClient)
        assert not booted.container.has(MockHttpClient)


def test_a_paced_client_needs_the_rate_limiter_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    # As without the throttling extra: the rate limiter bundle cannot be imported.
    monkeypatch.setitem(sys.modules, "xtr_rate_limiter.bundle", None)

    with pytest.raises(InvalidArgumentError, match="the rate limiter bundle is not active"):
        _ = Kernel(_UNPACED_APP, env="test", bundles={HttpClientBundle: {"all": True}}).build()
