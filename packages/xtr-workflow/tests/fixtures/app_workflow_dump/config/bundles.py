"""The application's root bundles: the console comes along; the article's guard needs security."""

from __future__ import annotations

from xtr_security.bundle import SecurityBundle

from xtr_workflow.bundle import WorkflowBundle

BUNDLES = {WorkflowBundle: {"all": True}, SecurityBundle: {"all": True}}
