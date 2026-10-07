"""JWT bundle builds and boots with env() placeholders in secret_key and issuer.

Verifies that the bundle does not evaluate env() placeholders during the build
phase, allowing applications to configure secret_key=env("file:...") and
issuer=env("JWT_ISSUER") as the README and the recipe template do, and that an
issuer resolving to nothing is refused where the manager is built.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.exception import ServiceResolutionError
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.bundle import JwtBundle
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_ISSUER = "https://jwt.test"


def _kernel(key_file: Path, issuer: str) -> Kernel:
    """Return a kernel whose JWT key and issuer both come from the environment."""
    return Kernel(
        "tests.fixtures.jwt_env_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
        environ={"JWT_TEST_KEY_PATH": str(key_file), "JWT_ISSUER": issuer},
    )


async def test_kernel_builds_and_boots_with_env_placeholder_in_secret_key(
    tmp_path: Path,
) -> None:
    """Kernel builds and boots when secret_key and issuer are env() placeholders.

    Writes a real RSA private key to a temp file, builds a kernel with
    JwtConfig(secret_key=env("file:JWT_TEST_KEY_PATH"), issuer=env("JWT_ISSUER")),
    boots it, resolves the token manager, and creates/verifies a token.
    """
    key_file = tmp_path / "private.pem"
    _ = key_file.write_text(RSA_PRIVATE_PEM)

    compiled = _kernel(key_file, _ISSUER).build()
    assert compiled is not None

    async with await compiled.boot() as booted:
        manager = await booted.container.get(JwtTokenManagerInterface)
        assert manager is not None

        user = InMemoryUser("test_user", roles=["ROLE_USER"])
        token = await manager.create(user)
        assert token is not None
        assert len(token) > 0

        claims = await manager.parse(token)
        assert claims is not None
        assert claims.get("username") == "test_user"
        roles = claims.get("roles", [])
        assert isinstance(roles, list) and "ROLE_USER" in roles
        assert claims.get("iss") == _ISSUER


async def test_manager_refuses_an_issuer_resolving_to_nothing(tmp_path: Path) -> None:
    """An empty JWT_ISSUER is refused where the manager is built, not at the build.

    The placeholder carries no value while the container compiles, so the build
    passes; the emptiness is caught when the manager is built and the
    variable is finally read.
    """
    key_file = tmp_path / "private.pem"
    _ = key_file.write_text(RSA_PRIVATE_PEM)

    compiled = _kernel(key_file, "").build()
    assert compiled is not None

    with pytest.raises(ServiceResolutionError, match="issuer cannot be empty"):
        _ = await compiled.boot()
