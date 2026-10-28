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
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.token_server import TokenServer

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle
from xtr_security_oauth2_server.exception import InvalidConfigurationError

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

    assert "config/packages/oauth2_server.py" in str(refusal)
    # The same one-liner the recipe's steps give: the base64url of 32 random
    # bytes, which is what ``encryption_key_type="key"`` reads.
    assert "base64.urlsafe_b64encode(secrets.token_bytes(32))" in str(refusal)
    assert "at least 32 characters" in str(refusal)


@pytest.mark.parametrize("service", UNSEALABLE, ids=_server_id)
async def test_the_refusal_does_not_point_at_the_command_that_mints_a_signing_key(
    service: type,
) -> None:
    # Two separate keys: one signs access tokens, the other seals this
    # server's own payloads. The key-pair command writes the signing pair as
    # PEM files and has nothing to do with this setting.
    async with await _unsealed().boot() as booted:
        refusal = await _refused(booted.container, service)

    assert "generate-keypair" not in str(refusal)
