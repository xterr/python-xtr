"""A template that is neither shipped nor a directory holding one."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["UnknownTemplateError"]


@final
class UnknownTemplateError(CliError):
    """``--template`` names no shipped template and no directory with a ``template.toml``.

    Attributes:
        template: The value given.
        available: The names of the templates that ship with this tool.
    """

    template: str
    available: tuple[str, ...]

    def __init__(self, template: str, available: tuple[str, ...]) -> None:
        """Record the value and what could have been chosen instead."""
        self.template = template
        self.available = available
        choices = ", ".join(available)
        super().__init__(f"no template {template!r}: choose {choices}, or a template directory")
