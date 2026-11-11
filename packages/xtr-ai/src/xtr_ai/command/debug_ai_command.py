"""``debug:ai``: the configured platforms and agents, never a secret."""

from __future__ import annotations

from typing import final

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import Injected, KernelInterface
from xtr_dependency_injection.config.env_placeholder import EnvPlaceholder

from xtr_ai.bundle.ai_config import AiConfig
from xtr_ai.bundle.toolset_configs import AgentToolRef

from ._registry import AI_COMMANDS

__all__ = ["DebugAiCommand"]


@as_command("debug:ai", registry=AI_COMMANDS)
@final
class DebugAiCommand:
    """List the platforms and agents as configured, before the environment is read."""

    async def __call__(self, io: ConsoleStyle, kernel: Injected[KernelInterface]) -> int:
        """Print each platform and each agent.

        The configuration is read as written: a value from the environment
        shows as ``env(NAME)``, and a key only says whether there is one.
        """
        config = next(
            (entry.value for entry in kernel.report.configs if isinstance(entry.value, AiConfig)),
            AiConfig(),
        )
        io.section("Platforms")
        if config.platforms:
            io.table(
                ("Name", "Provider", "API key", "Base URL"),
                [
                    (
                        escape(name),
                        _shown(platform.provider),
                        _key(platform.api_key),
                        _shown(platform.base_url) if platform.base_url is not None else "",
                    )
                    for name, platform in config.platforms.items()
                ],
            )
        else:
            io.text("No platform is configured.")
        io.section("Agents")
        if not config.agents:
            io.text("No agent is configured.")
            return ExitCode.SUCCESS
        rows: list[tuple[str, str, str, str, str]] = []
        for name, agent in config.agents.items():
            model = f"{_shown(agent.platform)}:{_shown(agent.model)}"
            fallbacks = ", ".join(escape(fallback.model_id) for fallback in agent.fallbacks)
            capabilities = ", ".join(_capability(entry) for entry in agent.capabilities)
            tools = ", ".join(
                escape(f"agent {entry.agent}")
                if isinstance(entry, AgentToolRef)
                else escape(entry.service.__qualname__)
                for entry in agent.toolsets
            )
            rows.append((escape(name), model, fallbacks, capabilities, tools))
        io.table(("Name", "Model", "Fallbacks", "Capabilities", "Toolsets"), rows)
        return ExitCode.SUCCESS


def _shown(value: str) -> str:
    """``value`` as written: ``env(NAME)`` for a placeholder, never what the variable holds."""
    return escape(repr(value) if isinstance(value, EnvPlaceholder) else value)


def _key(value: str | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, EnvPlaceholder):
        return escape(repr(value))
    return "set in the configuration"


def _capability(entry: object) -> str:
    if isinstance(entry, type):
        return escape(entry.__qualname__)
    if isinstance(entry, str):
        return escape(entry)
    if isinstance(entry, dict):
        return ", ".join(escape(str(key)) for key in entry)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType] — a declarative entry's keys are capability names
    return escape(type(entry).__qualname__)
