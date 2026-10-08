"""A template whose ``template.toml`` cannot be read as one."""

from __future__ import annotations

from typing import final

from .cli_error import CliError

__all__ = ["InvalidTemplateError"]


@final
class InvalidTemplateError(CliError):
    """A ``template.toml`` that does not parse, or holds a key or value it may not.

    Attributes:
        template: The template's name — its directory's name.
        reason: What is wrong, naming the key at fault.
    """

    template: str
    reason: str

    def __init__(self, template: str, reason: str) -> None:
        """Record the template and what is wrong with it."""
        self.template = template
        self.reason = reason
        super().__init__(f"template {template!r}: {reason}")
