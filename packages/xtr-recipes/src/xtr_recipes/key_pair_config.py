"""KeyPairConfig: a signing key a recipe has the sync mint into the project."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

__all__ = ["KEY_ALGORITHMS", "PROJECT_DIR", "KeyPairConfig"]

PROJECT_DIR: Final = "%kernel.project_dir%"
"""What a key's path variable starts with: the project root a key path is relative to."""

KEY_ALGORITHMS: Final = (
    "RS256",
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)
"""Every signature algorithm a key can be minted for.

The shared-secret algorithms are absent: they sign with a secret, which a
recipe generates as an ``[env]`` value instead.
"""


@final
@dataclass(frozen=True, slots=True)
class KeyPairConfig:
    """One ``[keys]`` entry: the private key to mint, and what encrypts it.

    Attributes:
        algorithm: The signature algorithm the key is for, one of
            :data:`KEY_ALGORITHMS`; it decides the key's type and size.
        passphrase: The ``[env]`` key whose generated secret the private key is
            encrypted with, or ``None`` to write it unencrypted.
        path_env: The ``[env]`` key the application reads the key's path from,
            whose default names this very key, or ``None`` when nothing does.
            A project that set it to another file has a key of its own, so none
            is minted for it.
    """

    algorithm: str
    passphrase: str | None = None
    path_env: str | None = None
