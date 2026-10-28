"""Console commands — needs xtr-console installed beside this package.

The workflow bundle registers them when the console bundle is active.
"""

from __future__ import annotations

from .workflow_dump_command import WorkflowDumpCommand

__all__ = ["WorkflowDumpCommand"]
