"""The application's root bundles: the security bundle comes along with the workflow bundle."""

from __future__ import annotations

from xtr_workflow.bundle import WorkflowBundle

BUNDLES = {WorkflowBundle: {"all": True}}
