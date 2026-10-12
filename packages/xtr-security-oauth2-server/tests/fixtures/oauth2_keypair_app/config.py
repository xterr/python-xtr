"""A deployment that keeps both halves of its signing key in files it names.

The uncommon shape, and the one the key-pair command has the most to write
for: a resource server running apart from the authorization server reads the
public half out of a file of its own, so both paths are configured and both
are written. The common deployment configures only the private one and has the
public half derived from it.
"""

from __future__ import annotations

from typing import Final

from xtr_dependency_injection import configure, env

from xtr_security_oauth2_server.bundle import (
    AuthorizationServerConfig,
    InMemoryPersistenceConfig,
    OAuth2ServerConfig,
    ResourceServerConfig,
    ScopesConfig,
)

__all__ = [
    "ALGORITHM",
    "PASSPHRASE",
    "PRIVATE_KEY_VARIABLE",
    "PUBLIC_KEY_VARIABLE",
    "oauth2_server",
]

PRIVATE_KEY_VARIABLE: Final[str] = "OAUTH2_SERVER_PRIVATE_KEY_PATH"
"""The file the signing key is read from, as the recipe names it."""

PUBLIC_KEY_VARIABLE: Final[str] = "OAUTH2_SERVER_PUBLIC_KEY_PATH"
"""The file the verifying key is read from, which only a split deployment sets."""

ALGORITHM: Final[str] = "ES256"
"""Not the default, so a run naming no algorithm is seen to read the configured one."""

PASSPHRASE: Final[str] = "the-pass-phrase-the-key-is-encrypted-with"
"""What the written private key is encrypted with, so the command is seen to apply it."""


@configure
def oauth2_server() -> OAuth2ServerConfig:
    """Sign with the key pair the two variables name."""
    return OAuth2ServerConfig(
        authorization_server=AuthorizationServerConfig(
            issuer="https://authorization.example.com",
            private_key=env(f"resolve:{PRIVATE_KEY_VARIABLE}"),
            private_key_passphrase=PASSPHRASE,
            encryption_key="a-password-long-enough-to-stretch-into-a-key",
            signature_algorithm=ALGORITHM,
            enable_device_code_grant=False,
        ),
        resource_server=ResourceServerConfig(public_key=env(f"resolve:{PUBLIC_KEY_VARIABLE}")),
        scopes=ScopesConfig(available=("read", "write"), default=("read",)),
        persistence=InMemoryPersistenceConfig(),
    )
