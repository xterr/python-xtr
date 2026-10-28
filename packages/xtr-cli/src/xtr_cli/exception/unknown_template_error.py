"""A template that does not ship with this tool."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["UnknownTemplateError"]


@final
class UnknownTemplateError(CliError):
    """No template ships under the name asked for.

    Attributes:
        template: The name asked for.
        available: The names of the templates that ship with this tool.
    """

    template: str
    available: tuple[str, ...]

    def __init__(self, template: str, available: tuple[str, ...]) -> None:
        """Record the name and what could have been chosen instead."""
        self.template = template
        self.available = available
        choices = ", ".join(available)
        super().__init__(f"no template {template!r}: choose {choices}")
