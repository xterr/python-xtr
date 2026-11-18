"""A data collector names a panel template that does not exist."""

from __future__ import annotations

from .web_profiler_error import WebProfilerError

__all__ = ["TemplateNotFoundError"]


class TemplateNotFoundError(WebProfilerError, LookupError):
    """A data collector names a panel template that does not exist.

    The template is named on the collector's tag as
    ``"@<import package>/<path under its templates folder>"``. Also a
    :class:`LookupError`.

    Attributes:
        collector: The collector whose panel could not be shown.
        template: The template its tag names.
    """

    collector: str
    template: str

    def __init__(self, collector: str, template: str) -> None:
        """Record the collector and the template it names."""
        self.collector = collector
        self.template = template
        super().__init__(
            f'the data collector "{collector}" names the template "{template}", which does '
            f'not exist; a template is named "@<import package>/<path under templates/>"'
        )
