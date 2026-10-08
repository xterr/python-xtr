"""The root every error in this library derives from."""

from __future__ import annotations

__all__ = ["CliError"]


class CliError(Exception):
    """Base class for every error raised by this library.

    Catch this to handle anything scaffolding a project can go wrong with; catch
    a subclass to handle one cause. Every subclass carries what went wrong as
    typed attributes and composes its own message from them.
    """
