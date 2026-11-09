"""The bundle builds and boots on its defaults, and cannot run without the server it extends."""

from __future__ import annotations

import sys

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import MissingBundleError
from xtr_dependency_injection.testing import assert_zero_config

from xtr_security_openid_connect_server.bundle import OpenIdConnectServerBundle

pytestmark = pytest.mark.anyio


def _bundle_alone() -> Kernel:
    """Return a kernel that lists this bundle and nothing else."""
    return Kernel(
        OpenIdConnectServerBundle.__module__,
        env="test",
        bundles={OpenIdConnectServerBundle: {"all": True}},
        resources=(),
    )


async def test_the_bundle_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(OpenIdConnectServerBundle)


async def test_listing_the_bundle_alone_brings_the_authorization_server_along() -> None:
    async with await _bundle_alone().boot() as booted:
        active = booted.kernel.bundles

    assert "oauth2_server" in active


def test_a_kernel_without_the_authorization_server_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # As without xtr-security-oauth2-server installed: its bundle cannot be imported.
    monkeypatch.setitem(sys.modules, "xtr_security_oauth2_server.bundle", None)

    with pytest.raises(
        MissingBundleError, match=r"oauth2_server.*required by openid_connect_server"
    ):
        _ = _bundle_alone().build()
