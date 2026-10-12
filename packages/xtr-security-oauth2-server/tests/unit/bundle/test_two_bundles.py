"""Both token bundles in one application, each keeping its own signing key.

The documented arrangement: a firewall signs the end user in with a self-issued
token while this server signs the access tokens an API reads. This is why this
package registers its key loader and JWS provider under a qualifier of its own
and never touches the unqualified names — those belong to the
self-issued-token package, and one bundle quietly signing with the other's key
would be impossible to notice from the outside.
"""

from __future__ import annotations

import pytest
from xtr_dependency_injection import Kernel
from xtr_security_jwt.bundle import JwtBundle
from xtr_security_jwt.services.jws_provider.jws_provider_interface import JwsProviderInterface
from xtr_security_jwt.services.key_loader.key_loader_interface import KeyLoaderInterface

from tests.fixtures.oauth2_with_jwt_app.config import JWT_SECRET
from tests.support.signing import SIGNING_KEY_PEM
from xtr_security_oauth2_server.authorization_server import AuthorizationServer
from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

pytestmark = pytest.mark.anyio

#: What this package registers its own key services under.
QUALIFIER = "oauth2_server"


def _kernel() -> Kernel:
    """Return a kernel running both token bundles."""
    return Kernel(
        "tests.fixtures.oauth2_with_jwt_app",
        env="test",
        bundles={JwtBundle: {"all": True}, OAuth2ServerBundle: {"all": True}},
        concurrent_scoped_access=True,
    )


async def test_both_bundles_build_and_boot_together() -> None:
    async with await _kernel().boot() as booted:
        assert booted.container is not None


async def test_the_unqualified_key_belongs_to_the_self_issued_token_package() -> None:
    async with await _kernel().boot() as booted:
        loader = await booted.container.get(KeyLoaderInterface)

    assert loader.get_signing_key() == JWT_SECRET


async def test_this_package_reads_its_own_key_under_its_own_qualifier() -> None:
    async with await _kernel().boot() as booted:
        loader = await booted.container.get(KeyLoaderInterface, QUALIFIER)

    assert loader.get_signing_key() == SIGNING_KEY_PEM


async def test_neither_bundle_signs_with_the_others_key() -> None:
    # The one thing this arrangement has to guarantee.
    async with await _kernel().boot() as booted:
        login = await booted.container.get(KeyLoaderInterface)
        access = await booted.container.get(KeyLoaderInterface, QUALIFIER)

    assert login.get_signing_key() != access.get_signing_key()


async def test_each_bundle_has_a_provider_of_its_own() -> None:
    async with await _kernel().boot() as booted:
        login = await booted.container.get(JwsProviderInterface)
        access = await booted.container.get(JwsProviderInterface, QUALIFIER)

    assert login is not access


async def test_this_servers_own_wiring_still_stands_beside_the_other_bundle() -> None:
    async with await _kernel().boot() as booted:
        server = await booted.container.get(AuthorizationServer)

    assert "client_credentials" in repr(server)
