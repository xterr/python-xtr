"""Everything this library raises, under :class:`WebProfilerError`."""

from __future__ import annotations

from .invalid_argument_error import InvalidArgumentError
from .template_not_found_error import TemplateNotFoundError
from .web_profiler_error import WebProfilerError

__all__ = ["InvalidArgumentError", "TemplateNotFoundError", "WebProfilerError"]
