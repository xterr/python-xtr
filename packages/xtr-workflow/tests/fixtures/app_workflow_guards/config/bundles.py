"""The application's root bundles: its guards need the security bundle listed too."""

from __future__ import annotations

from xtr_security.bundle import SecurityBundle

from xtr_workflow.bundle import WorkflowBundle

BUNDLES = {WorkflowBundle: {"all": True}, SecurityBundle: {"all": True}}
