"""Writing a project file safely: never through a link, secrets never world-readable."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .exception import UnsafePathError

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ENV_NAME", "refuse_symlink", "write_text"]

ENV_NAME = ".env"
"""The one file a recipe writes that holds secrets, created ``0o600``."""

_PRIVATE_FLAGS = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
_PRIVATE_MODE = 0o600


def refuse_symlink(path: Path) -> None:
    """Refuse a target that is a symbolic link.

    Every write resolves a link out of the project, so following one would let
    a planted link redirect a recipe's write anywhere on disk. A link is
    refused rather than written through.

    Raises:
        UnsafePathError: When ``path`` is a symbolic link.
    """
    if path.is_symlink():
        raise UnsafePathError(path, "is a symbolic link")


def write_text(path: Path, text: str, *, private: bool = False) -> None:
    """Write ``text`` to ``path``, creating the directories above it.

    Args:
        path: Where the file goes; refused when it is a symbolic link.
        text: The content to write.
        private: Whether a file created here is for the owner alone
            (``0o600``) — the recipe-written ``.env`` carries secrets. An
            existing file keeps the mode it has; only creation sets it.

    Raises:
        UnsafePathError: When ``path`` is a symbolic link.
    """
    refuse_symlink(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if private:
        descriptor = os.open(path, _PRIVATE_FLAGS, _PRIVATE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            _ = handle.write(text)
    else:
        _ = path.write_text(text, encoding="utf-8")
