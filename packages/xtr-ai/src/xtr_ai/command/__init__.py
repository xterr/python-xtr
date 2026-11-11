"""Console commands, registered when the console bundle is active."""

from __future__ import annotations

from .agent_call_command import AgentCallCommand
from .debug_ai_command import DebugAiCommand
from .platform_invoke_command import PlatformInvokeCommand

__all__ = ["AgentCallCommand", "DebugAiCommand", "PlatformInvokeCommand"]
