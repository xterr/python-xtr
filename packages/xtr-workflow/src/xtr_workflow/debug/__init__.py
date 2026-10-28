"""Seeing what a workflow did: the calls it was asked, and who listens to its steps.

:class:`TraceableWorkflow` wraps a workflow and records every call that may
ask its listeners — what was asked, how long it took, what came back.

Listing who listens to each place and transition of a workflow, for the
tools that draw one, is internal: it is imported from
:mod:`xtr_workflow.debug.listener_extractor` and not from here.
"""

from __future__ import annotations

from .traceable_workflow import TraceableWorkflow

__all__ = ["TraceableWorkflow"]
