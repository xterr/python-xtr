"""Telling which subjects a workflow moves, so a registry can find the workflow of one."""

from __future__ import annotations

from .instance_of_support_strategy import InstanceOfSupportStrategy
from .workflow_support_strategy_interface import WorkflowSupportStrategyInterface

__all__ = ["InstanceOfSupportStrategy", "WorkflowSupportStrategyInterface"]
