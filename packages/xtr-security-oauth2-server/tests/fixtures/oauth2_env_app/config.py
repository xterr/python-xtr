"""A deployment configured the way this package's recipe writes it.

Both pieces of key material come out of the environment: the signing key as the
path of the file holding it, and the key this server's own payloads are sealed
with as the base64url of its bytes. Neither is read while the container is
built — a variable is read when the service needing it is built — so this is
also what keeps a fresh application's console running before either is set.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure, env

from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ScopesConfig,
)

__all__ = ["ENCRYPTION_KEY_VARIABLE", "ISSUER", "PRIVATE_KEY_VARIABLE", "oauth2_server"]

PRIVATE_KEY_VARIABLE: Final[str] = "OAUTH2_SERVER_PRIVATE_KEY_PATH"
"""The file the signing key is read from, as the recipe names it."""

ENCRYPTION_KEY_VARIABLE: Final[str] = "OAUTH2_SERVER_ENCRYPTION_KEY"
"""The key the authorization codes and refresh tokens are sealed with."""

ISSUER: Final[str] = "https://authorization.example.com"
"""The origin every token of this deployment claims to come from."""


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Sign with the key the path names, and seal with the key the variable carries."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            issuer=ISSUER,
            private_key=env(f"resolve:{PRIVATE_KEY_VARIABLE}"),
            encryption_key=env(ENCRYPTION_KEY_VARIABLE),
            encryption_key_type="key",
            enable_device_code_grant=False,
        ),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
