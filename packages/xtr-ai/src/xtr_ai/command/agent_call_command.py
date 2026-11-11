"""``ai:agent:call``: a conversation with an agent, held in memory."""

from __future__ import annotations

from collections.abc import Hashable
from typing import Any, final

from pydantic_ai.agent import AbstractAgent
from pydantic_ai.conversation import Conversation
from pydantic_ai.exceptions import AgentRunError, ModelAPIError, UserError
from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import ServiceLocator
from xtr_dependency_injection.exception import UnknownLocatorKeyError

from xtr_ai.exception import AiError

from ._registry import AI_COMMANDS

__all__ = ["AgentCallCommand"]


@as_command("ai:agent:call", registry=AI_COMMANDS)
@final
class AgentCallCommand:
    """Talk to an agent; an empty line ends the conversation."""

    __slots__ = ("_agents",)

    # The container keys agents by the bare class, so the parameter names it bare.
    def __init__(self, agents: ServiceLocator[AbstractAgent]) -> None:
        """Reach the configured agents through ``agents``."""
        self._agents: ServiceLocator[AbstractAgent[Any, Any]] = agents

    async def __call__(self, io: ConsoleStyle, agent: str) -> int:
        """Ask, answer, and ask again, keeping the conversation in memory.

        Args:
            io: Where the command reads and writes.
            agent: The configured agent to talk to.
        """
        key: Hashable = agent
        try:
            chosen = await self._agents.get(key)
        except UnknownLocatorKeyError:
            io.error(f"No agent is configured under {escape(agent)!r}.")
            return ExitCode.INVALID
        conversation: Conversation | None = None
        while prompt := io.ask("You").strip():
            try:
                result = await chosen.run(prompt, conversation=conversation)
            except (AiError, AgentRunError, ModelAPIError, UserError) as error:
                io.error(escape(str(error)))
                return ExitCode.FAILURE
            conversation = result.conversation
            io.text(f"[bold]{escape(agent)}[/bold]: {escape(str(result.output))}")
        return ExitCode.SUCCESS
