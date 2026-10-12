"""The bundle builds and boots on its defaults, and says what is missing when used."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_dependency_injection.testing import assert_zero_config
from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.controller.metadata_controller import MetadataController
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.manager.scope_manager_interface import ScopeManagerInterface
from xtr_security_oauth2_server.service.credentials_revoker_interface import (
    CredentialsRevokerInterface,
)

if TYPE_CHECKING:
    from collections.abc import Hashable

    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

#: What the package's own key loader and JWS provider are registered under.
QUALIFIER = "oauth2_server"


def _unconfigured() -> Kernel:
    """Return a kernel that lists the bundle and configures nothing."""
    return Kernel(
        "tests.fixtures.oauth2_unconfigured_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )


async def _refused(
    container: ContainerInterface,
    service: type[object],
    qualifier: Hashable | None = None,
) -> InvalidConfigurationError:
    """Return the configuration refusal asking for ``service`` reports.

    The container wraps whatever a factory raised, so what a deployment reads
    is the refusal's own message inside the container's report; this unwraps it
    and checks it really is one of ours.
    """
    with pytest.raises(ServiceResolutionError) as reported:
        _ = await container.get(service, qualifier)
    cause = reported.value.__cause__
    assert isinstance(cause, InvalidConfigurationError)

    return cause


async def test_the_bundle_builds_and_boots_with_no_configuration() -> None:
    await assert_zero_config(OAuth2ServerBundle)


async def test_an_application_that_configures_nothing_still_gets_a_container() -> None:
    async with await _unconfigured().boot() as booted:
        assert booted.container is not None


async def test_asking_for_a_store_names_the_persistence_setting() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, ClientManagerInterface)

    assert "persistence is not configured" in str(refusal)


async def test_asking_for_the_revoker_names_the_persistence_setting_too() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, CredentialsRevokerInterface)

    assert "persistence is not configured" in str(refusal)


async def test_the_persistence_refusal_names_the_file_to_write_it_in() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, ClientManagerInterface)

    assert "config/oauth2_server.py" in str(refusal)


async def test_asking_for_a_key_names_the_private_key_setting() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, KeyLoaderInterface, QUALIFIER)

    assert "authorization_server.private_key" in str(refusal)


async def test_asking_for_the_scopes_names_the_available_setting() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, ScopeManagerInterface)

    assert "scopes.available" in str(refusal)


async def test_asking_for_the_description_names_the_issuer_setting() -> None:
    async with await _unconfigured().boot() as booted:
        refusal = await _refused(booted.container, MetadataController)

    assert "authorization_server.issuer" in str(refusal)
