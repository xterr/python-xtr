"""Reporting a key file that is not there in this server's terms, not the token package's.

The key loader belongs to the self-issued-token package, and so does the error
it raises for a missing key file: worded for that package's settings and its
own command. Everything here that reads a key through the loader turns that
error into this one, naming this server's setting and the command that mints
the key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server.exception.invalid_configuration_error import (
    InvalidConfigurationError,
)

if TYPE_CHECKING:
    from xtr_security_jwt.exception import MissingKeyError

__all__ = ["MINT_COMMAND", "missing_key_file"]

#: The command that mints the key pair where the configuration points.
MINT_COMMAND: Final = "oauth2-server:generate-keypair"

#: Where an application writes this server's configuration — the file every
#: refusal of this package points at.
_CONFIG_FILE: Final = "<app>/config/packages/oauth2_server.py"


def missing_key_file(
    missing: MissingKeyError,
    setting: str,
    because: str,
    source: str = "",
) -> InvalidConfigurationError:
    """Return the refusal for the key file ``setting`` names and that is not there.

    Args:
        missing: What the key loader raised, naming the file it looked for.
        setting: The setting that names the file.
        because: What cannot be done without it, as a clause.
        source: Where the written configuration reads the setting from, as a
            clause beginning with a dash, or empty when it reads it from nowhere.
    """
    return InvalidConfigurationError(
        f"The key file {missing.location!r} that {setting} names does not exist, so {because}. "
        f"Point the setting at the key in {_CONFIG_FILE}{source}, or mint the key there with "
        f"'{MINT_COMMAND}'.",
    )
