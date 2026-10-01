"""JWT bundle builds and boots with env() placeholder in secret_key.

Verifies that the bundle does not evaluate env() placeholders during the build
phase, allowing applications to configure secret_key=env("file:...") as documented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import Kernel
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.keys import RSA_PRIVATE_PEM
from xtr_security_jwt.bundle import JwtBundle
from xtr_security_jwt.services.jwt_token_manager_interface import JwtTokenManagerInterface

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


async def test_kernel_builds_and_boots_with_env_placeholder_in_secret_key(
    tmp_path: Path,
) -> None:
    """Kernel builds and boots when secret_key is env("file:...") placeholder.

    Writes a real RSA private key to a temp file, builds a kernel with
    JwtConfig(secret_key=env("file:JWT_TEST_KEY_PATH")), boots it, resolves
    the token manager, and creates/verifies a token.
    """
    key_file = tmp_path / "private.pem"
    _ = key_file.write_text(RSA_PRIVATE_PEM)

    kernel = Kernel(
        "tests.fixtures.jwt_env_app",
        env="test",
        bundles={JwtBundle: {"all": True}},
        concurrent_scoped_access=True,
        environ={"JWT_TEST_KEY_PATH": str(key_file)},
    )

    compiled = kernel.build()
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
