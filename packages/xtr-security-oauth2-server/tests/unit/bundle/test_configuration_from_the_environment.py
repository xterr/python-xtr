"""Key material a deployment keeps in its environment, which is how the recipe writes it.

A variable is read when the service needing it is built, never while the
container is: so an application whose key material is not there yet still
gets a container — and its console — and the servers are built from the real
values once it is.
"""

from __future__ import annotations

import base64
import secrets
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.token_server import TokenServer

from tests.fixtures.oauth2_env_app.config import (
    ENCRYPTION_KEY_VARIABLE,
    PRIVATE_KEY_VARIABLE,
)
from tests.support.signing import SIGNING_KEY_PEM
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

pytestmark = pytest.mark.anyio

#: Both servers seal or unseal this server's own payloads, so both read the key.
SEALING = (AuthorizationServer, TokenServer)

_APP = "tests.fixtures.oauth2_env_app"


def _server_id(service: type) -> str:
    """Name a parametrised case after the server it asks for."""
    return service.__name__


def _kernel(environ: Mapping[str, str] | None = None) -> Kernel:
    """Return a kernel of the environment-configured deployment."""
    return Kernel(
        _APP,
        env="test",
        bundles={OAuth2ServerBundle: {"all": True}},
        environ=dict(environ) if environ is not None else None,
    )


def _described(tmp_path: Path) -> dict[str, str]:
    """Write the signing key where the configuration reads it, and name both variables."""
    key_file = tmp_path / "oauth2.pem"
    _ = key_file.write_text(SIGNING_KEY_PEM, encoding="utf-8")

    return {
        PRIVATE_KEY_VARIABLE: str(key_file),
        # The base64url of 32 random bytes, which is what the 'key' kind is.
        ENCRYPTION_KEY_VARIABLE: base64.urlsafe_b64encode(secrets.token_bytes(32))
        .decode()
        .rstrip("="),
    }


@pytest.mark.parametrize("service", SEALING, ids=_server_id)
async def test_the_variables_are_read_where_each_server_is_built(
    service: type,
    tmp_path: Path,
) -> None:
    async with await _kernel(_described(tmp_path)).boot() as booted:
        assert await booted.container.get(service) is not None


async def test_an_application_whose_variables_are_not_set_yet_still_gets_a_container() -> None:
    # What keeps the console running on a fresh checkout: nothing reads either
    # variable while the container is built.
    async with await _kernel().boot() as booted:
        assert booted.container is not None
