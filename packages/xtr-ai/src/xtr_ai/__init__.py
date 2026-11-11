"""Named language-model platforms and agents built on pydantic-ai.

A *platform* is one configured provider — its key, its endpoint, its options —
built the first time a run needs it. An agent's model id is
``<platform>:<model>``, resolved through the platforms, so a model is chosen per
environment without a code change. Run control reports what a run is doing and
cancels it from another process.

Applications keep working with pydantic-ai's own types: an ``AbstractAgent``,
a ``ConversationStore``. Everything here can be built by hand; the container
integration lives in :mod:`xtr_ai.bundle`.
"""

from __future__ import annotations

from .agent_tool import agent_toolset
from .decorator import as_tool, service_toolset
from .exception import AiError, InvalidConfigurationError, PlatformUnavailableError
from .platform import Platform
from .platform_interface import PlatformInterface
from .platform_registry import PlatformRegistry
from .platform_registry_interface import PlatformRegistryInterface
from .run_clock import RunClock
from .run_defaults_agent import RunDefaultsAgent
from .run_logging import RunLogging

__all__ = [
    "AiError",
    "InvalidConfigurationError",
    "Platform",
    "PlatformInterface",
    "PlatformRegistry",
    "PlatformRegistryInterface",
    "PlatformUnavailableError",
    "RunClock",
    "RunDefaultsAgent",
    "RunLogging",
    "agent_toolset",
    "as_tool",
    "service_toolset",
]
