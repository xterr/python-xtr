"""The profiler panel's collector: every email a profiled request sent or queued.

It records into the http kernel's per-request trace, so importing it needs xtr-http-kernel;
the bundle registers it only when the http kernel profiles requests.
"""

from __future__ import annotations

from .mailer_data_collector import MailerDataCollector

__all__ = ["MailerDataCollector"]
