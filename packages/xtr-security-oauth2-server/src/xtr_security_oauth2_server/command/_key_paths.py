"""Turning the configured key material into the files a key pair is written to.

A deployment configures its keys as the key text or as the path of a file
holding it, and the key loader tells the two apart by whether the value opens a
PEM. The key-pair command can only write the second kind, so this is where that
question is asked — and where a deployment configuring the first kind, or
nothing at all, is told which setting leaves nowhere to write.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

__all__ = ["private_key_path", "public_key_path"]

#: Where an application writes this bundle's configuration.
_CONFIG_FILE: Final = "<app>/config/packages/oauth2_server.py"

#: What tells key text from the path of a file holding it, the way the key
#: loader tells them apart.
_PEM_MARKER: Final = "-----BEGIN"


def private_key_path(configured: str) -> Path:
    """Return the file the signing key is written to.

    Raises:
        InvalidConfigurationError: When nothing is configured, so there is
            nowhere to write; or when what is configured is the key text
            itself, which is already a key and names no file.
    """
    if not configured:
        raise InvalidConfigurationError(
            "The setting authorization_server.private_key is not configured, so there is "
            f"nowhere to write a signing key. Write it in {_CONFIG_FILE} as the path of the "
            "file this deployment reads its key from.",
        )
    if _PEM_MARKER in configured:
        raise InvalidConfigurationError(
            "The setting authorization_server.private_key holds the key text itself rather "
            f"than the path of a file, so there is nothing to write. Point it at a file in "
            f"{_CONFIG_FILE} to have the pair written for you.",
        )

    return Path(configured)


def public_key_path(configured: str) -> Path | None:
    """Return the file the verifying key is written to, or ``None`` when there is none.

    Nothing is the common answer: a deployment that named no verifying key has
    it derived from the signing one, so there is no second file to write.

    Raises:
        InvalidConfigurationError: When what is configured is the key text
            itself, which names no file.
    """
    if not configured:
        return None
    if _PEM_MARKER in configured:
        raise InvalidConfigurationError(
            "The setting resource_server.public_key holds the key text itself rather than "
            f"the path of a file, so there is nothing to write. Point it at a file in "
            f"{_CONFIG_FILE}, or leave it unset to have the verifying key derived from the "
            "signing one.",
        )

    return Path(configured)
