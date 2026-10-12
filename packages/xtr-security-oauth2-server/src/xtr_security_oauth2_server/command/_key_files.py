"""Writing a minted key pair into the files a deployment configured.

Every write goes through a descriptor opened ``O_NOFOLLOW``, so a symbolic
link planted where a key file is about to land cannot redirect it to whatever
it points at; and the private file's mode is set on the descriptor before a
byte reaches it, so a signing key never sits world-readable even briefly.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["PRIVATE_MODE", "PUBLIC_MODE", "write_key_file"]

PRIVATE_MODE: Final = 0o600
"""The mode the private key is written at: readable by its owner alone."""

PUBLIC_MODE: Final = 0o644
"""The mode the public key is written at: it is published, so it is readable."""

#: The mode every directory this write brings into being is left at.
_DIRECTORY_MODE: Final = 0o700


def write_key_file(path: Path, text: str, mode: int) -> None:
    """Write ``text`` into ``path`` at ``mode``, creating the directories it needs.

    Replaces whatever is already there: whether a key file in place may be
    replaced at all is the caller's question, asked and answered before this
    is reached.

    Raises:
        InvalidArgumentError: When the path cannot be opened as a regular file
            this call may write — it is a symbolic link, a directory, or
            somewhere the process is not allowed to write.
    """
    _create_private_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, mode)
    except OSError as error:
        raise InvalidArgumentError(
            f"{path} could not be opened as a regular file to write ({error}); a key is "
            "never written through a symbolic link.",
        ) from error
    try:
        os.fchmod(descriptor, mode)
        _ = os.write(descriptor, text.encode("utf-8"))
    finally:
        os.close(descriptor)


def _create_private_directory(directory: Path) -> None:
    """Create ``directory`` and every missing parent, each left owner-only (``0o700``).

    ``mkdir``'s mode is narrowed by the process umask, so each directory this
    call brings into being has its mode set afterwards — through a descriptor
    that refuses to follow a link, so a directory swapped for a symbolic link
    between the two steps cannot redirect the change. A directory that already
    existed is left exactly as it is: its mode is the deployment's to choose,
    not this command's to tighten.
    """
    for one in reversed([directory, *directory.parents]):
        if one.exists():
            continue
        try:
            one.mkdir(mode=_DIRECTORY_MODE)
        except FileExistsError:  # another writer won the race, and owns the mode
            continue
        _make_directory_private(one)


def _make_directory_private(directory: Path) -> None:
    """Set ``directory`` owner-only through a descriptor that refuses to follow a link."""
    descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchmod(descriptor, _DIRECTORY_MODE)
    finally:
        os.close(descriptor)
