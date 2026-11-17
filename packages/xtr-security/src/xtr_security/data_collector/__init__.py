"""The security panel of the profiler: the firewall, the token, the authenticators, the votes.

:class:`SecurityDataCollector` is registered by the bundle when the http
kernel profiles requests; the decisions and the authenticators it shows are
reported to it by the traceable decision manager and manager listeners, so
they appear when tracing is on.
"""

from __future__ import annotations

from .security_data_collector import SecurityDataCollector

__all__ = ["SecurityDataCollector"]
