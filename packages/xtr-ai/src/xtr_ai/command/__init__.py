"""Console commands, registered when the console bundle is active.

``ai:run:cancel`` lives in its own module, scanned only when run control is
configured.
"""

from __future__ import annotations

from .agent_call_command import AgentCallCommand
from .debug_ai_command import DebugAiCommand
from .platform_invoke_command import PlatformInvokeCommand

__all__ = ["AgentCallCommand", "DebugAiCommand", "PlatformInvokeCommand"]
