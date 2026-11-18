"""The profiler panel of the workflow calls a profiled request made.

:class:`WorkflowDataCollector` shows the workflows the application defines and
keeps each call the traced workflows answer while the http kernel's profiler
records a request. It needs xtr-http-kernel, so only the bundle imports it, and
only when that kernel's profiler is on in debug mode.
"""

from __future__ import annotations

from .workflow_data_collector import WorkflowDataCollector

__all__ = ["WorkflowDataCollector"]
