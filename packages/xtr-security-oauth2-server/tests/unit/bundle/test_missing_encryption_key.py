"""A deployment that described everything but the seal on its own payloads.

An authorization code and a refresh token are this server's own payloads
handed to a client, sealed with a key only the deployment holds. Both servers
read that key when they are built — never when the container is, so the
console still runs and can mint one — and each refuses by naming the setting
and the file it belongs in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import ServiceResolutionError

from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.exception import InvalidConfigurationError
from xtr_security_oauth2_server.token_server import TokenServer

if TYPE_CHECKING:
    from xtr_service_contracts import ContainerInterface

pytestmark = pytest.mark.anyio

#: The two servers, each of which seals or unseals a payload of this server's.
UNSEALABLE = (AuthorizationServer, TokenServer)


def _server_id(service: type) -> str:
    """Name a parametrised case after the server it asks for."""
    return service.__name__


def _unsealed() -> Kernel:
    """Return a kernel of the deployment that named no encryption key."""
    return Kernel(
        "tests.fixtures.oauth2_unsealed_app",
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
    )


async def _refused(
    container: ContainerInterface,
    service: type[object],
) -> InvalidConfigurationError:
    """Return the configuration refusal asking for ``service`` reports.

    The container wraps whatever a factory raised, so what a deployment reads
    is the refusal's own message inside the container's report; this unwraps it
    and checks it really is one of ours.
    """
    with pytest.raises(ServiceResolutionError) as reported:
        _ = await container.get(service)
    cause = reported.value.__cause__
    assert isinstance(cause, InvalidConfigurationError)

    return cause


async def test_a_deployment_that_named_no_encryption_key_still_gets_a_container() -> None:
    async with await _unsealed().boot() as booted:
        assert booted.container is not None


@pytest.mark.parametrize("service", UNSEALABLE, ids=_server_id)
async def test_asking_for_a_server_names_the_encryption_key_setting(service: type) -> None:
    async with await _unsealed().boot() as booted:
        refusal = await _refused(booted.container, service)

    assert "authorization_server.encryption_key" in str(refusal)


@pytest.mark.parametrize("service", UNSEALABLE, ids=_server_id)
async def test_the_refusal_says_what_cannot_be_done_without_it(service: type) -> None:
    async with await _unsealed().boot() as booted:
        refusal = await _refused(booted.container, service)

    assert "no key to seal them with" in str(refusal)


@pytest.mark.parametrize("service", UNSEALABLE, ids=_server_id)
async def test_the_refusal_says_where_to_write_it_and_how_to_come_by_one(service: type) -> None:
    async with await _unsealed().boot() as booted:
        refusal = await _refused(booted.container, service)

    assert "config/oauth2_server.py" in str(refusal)
    assert "oauth2-server:generate-keypair" in str(refusal)
