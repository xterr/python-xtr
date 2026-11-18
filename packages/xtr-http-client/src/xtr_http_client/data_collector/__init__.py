"""The profiler panel of the outgoing HTTP requests a profiled request made.

:class:`HttpClientDataCollector` keeps each request the bundle's clients make
while the http kernel's profiler records a request. It needs xtr-http-kernel,
so only the bundle imports it, and only when that kernel's profiler is on.
"""

from __future__ import annotations

from .http_client_data_collector import HttpClientDataCollector

__all__ = ["HttpClientDataCollector"]
