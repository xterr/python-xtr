"""The application's root bundles: the console and the security bundle come along."""

from __future__ import annotations

from xtr_workflow.bundle import WorkflowBundle

BUNDLES = {WorkflowBundle: {"all": True}}
