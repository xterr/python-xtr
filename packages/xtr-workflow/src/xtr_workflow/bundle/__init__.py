"""The configuration of the xtr-dependency-injection bundle for xtr-workflow."""

from __future__ import annotations

from .arc_config import ArcConfig
from .audit_trail_config import AuditTrailConfig
from .marking_store_config import MarkingStoreConfig
from .place_config import PlaceConfig
from .transition_config import TransitionConfig
from .workflow_config import WorkflowConfig
from .workflow_definition_config import WorkflowDefinitionConfig

__all__ = [
    "ArcConfig",
    "AuditTrailConfig",
    "MarkingStoreConfig",
    "PlaceConfig",
    "TransitionConfig",
    "WorkflowConfig",
    "WorkflowDefinitionConfig",
]
