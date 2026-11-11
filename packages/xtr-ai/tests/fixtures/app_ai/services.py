"""A tool service, a capability with a dependency, and the scripted model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)
from typing_extensions import override
from xtr_dependency_injection import as_service

from xtr_ai import as_tool

if TYPE_CHECKING:
    from pydantic_ai.models.function import AgentInfo


@as_service
class Directory:
    """A dependency the tool service and the capability are injected with."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {"ada": "Ada Lovelace"}


class People:
    """Tools the chat agent calls."""

    def __init__(self, directory: Directory) -> None:
        self._directory: Directory = directory

    @as_tool(agents=("chat",))
    def full_name(self, short: str) -> str:
        """The full name of someone known by a short name."""
        return self._directory.names.get(short, "unknown")


@dataclass
class Greeting(AbstractCapability[Any]):
    """Adds instructions naming who it was built with, to prove injection."""

    directory: Directory

    @override
    def get_instructions(self) -> str:
        return f"Greet {self.directory.names['ada']}."

    @classmethod
    @override
    def get_serialization_name(cls) -> str | None:
        return None


def scripted(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Call ``full_name``, then ``research``, then answer with what both returned."""
    returned = [
        part.content
        for message in messages
        if isinstance(message, ModelRequest)
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]
    tools = {tool.name for tool in info.function_tools}
    if not returned and "full_name" in tools:
        return ModelResponse(parts=[ToolCallPart("full_name", {"short": "ada"})])
    if len(returned) == 1 and "research" in tools:
        return ModelResponse(parts=[ToolCallPart("research", {"prompt": "who?"})])
    instructions = info.instructions or ""
    return ModelResponse(parts=[TextPart(f"{returned} | {instructions}")])


def echo_settings(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    """Answer with the settings the request was sent with."""
    del messages
    return ModelResponse(parts=[TextPart(f"settings: {info.model_settings}")])
