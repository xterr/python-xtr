"""A development toolbar on every page, and a profile of every request.

In the development environment, each HTML page an application serves gets a
toolbar at its foot: the status, the time it took, the memory, the log, the
events, the route, the background requests the page made since. Each item
opens the request's full profile — request and response, a timeline of where
the time went, every log record, every listener, the exception with its
frames — and every profile stays searchable for two days.

The profiles are collected by the http kernel's profiler; this package draws
them. A library adds a panel by registering a data collector with a template.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .controller.profiler_controller import PROFILER_PAGE_HEADER, ProfilerController
from .exception import InvalidArgumentError, TemplateNotFoundError, WebProfilerError
from .profiler.collector_view import CollectorView
from .profiler.template_manager import TemplateManager
from .web_debug_toolbar_middleware import WebDebugToolbarMiddleware

try:
    __version__ = version("xtr-web-profiler")
except PackageNotFoundError:  # pragma: no cover
    # Running from a source tree with no installed metadata to read.
    __version__ = "0+unknown"

__all__ = [
    "PROFILER_PAGE_HEADER",
    "CollectorView",
    "InvalidArgumentError",
    "ProfilerController",
    "TemplateManager",
    "TemplateNotFoundError",
    "WebDebugToolbarMiddleware",
    "WebProfilerError",
    "__version__",
]
