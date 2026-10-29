"""Python source rendered from a template that does not parse."""

from __future__ import annotations

from .maker_error import MakerError

__all__ = ["GeneratedSourceError"]


class GeneratedSourceError(MakerError):
    """Python source rendered from a template that does not parse.

    A template is checked every time it renders, so a broken one — or a value
    that broke it — is reported against the template, never written into the
    application for the next import to trip over.

    Attributes:
        template: The template that rendered the source.
        reason: What the parser reported.
        line: The line of the rendered source it reported, when it named one.
    """

    template: str
    reason: str
    line: int | None

    def __init__(self, template: str, reason: str, line: int | None = None) -> None:
        """Record the template, the parser's message and the line it pointed at."""
        self.template = template
        self.reason = reason
        self.line = line
        where = f"{template}:{line}" if line is not None else template
        super().__init__(f"{where}: the rendered source does not parse: {reason}")
