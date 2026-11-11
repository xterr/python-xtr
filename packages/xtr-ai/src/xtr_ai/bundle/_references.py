"""What the bundle refuses before it registers anything."""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

from xtr_ai.exception import InvalidConfigurationError

from ._placeholder import is_literal
from .toolset_configs import AgentToolRef

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .ai_config import AiConfig

__all__ = ["check_references", "require_bridge"]


def require_bridge(what: str, bridge: str, *, orm_active: bool) -> None:
    """Refuse an orm adapter whose bridge package is missing, or whose orm is not active.

    Whether the orm bundle runs is the application's call: installing xtr-orm
    does not activate it, so an adapter needing it names what to list.

    Raises:
        InvalidConfigurationError: Naming the package to install, or the
            bundle to list.
    """
    if find_spec(bridge) is None:
        package = bridge.replace("_", "-")
        raise InvalidConfigurationError(
            f'{what} uses the orm, which needs the {package} package: uv add "xtr-ai[orm]".',
        )
    if not orm_active:
        raise InvalidConfigurationError(
            f"{what} uses the orm, but OrmBundle is not active: list it beside AiBundle "
            "in the application's bundles.",
        )


def check_references(config: AiConfig) -> None:
    """Refuse a literal reference to a platform or agent that is not configured, and agent cycles.

    Raises:
        InvalidConfigurationError: Naming the agent and what it names.
    """
    platforms = set(config.platforms)
    calls: dict[str, set[str]] = {}
    for name, agent in config.agents.items():
        named = [agent.platform, *(fallback.platform for fallback in agent.fallbacks)]
        for platform in named:
            if is_literal(platform) and platform not in platforms:
                raise InvalidConfigurationError(
                    f'The "{name}" agent names the "{platform}" platform, which is not configured.',
                )
        calls[name] = {entry.agent for entry in agent.toolsets if isinstance(entry, AgentToolRef)}
        for called in calls[name]:
            if called not in config.agents:
                raise InvalidConfigurationError(
                    f'The "{name}" agent calls the "{called}" agent, which is not configured.',
                )
    for name in calls:
        _refuse_cycle(name, calls, ())


def _refuse_cycle(name: str, calls: Mapping[str, set[str]], path: tuple[str, ...]) -> None:
    if name in path:
        cycle = " -> ".join((*path[path.index(name) :], name))
        raise InvalidConfigurationError(f"Agents call each other in a cycle: {cycle}.")
    for called in sorted(calls.get(name, ())):
        _refuse_cycle(called, calls, (*path, name))
