"""``ai:platform:invoke``: one request to a model of a platform."""

from __future__ import annotations

from typing import final

from pydantic_ai.direct import model_request
from pydantic_ai.exceptions import ModelAPIError
from pydantic_ai.messages import ModelRequest, TextPart
from xtr_console import ConsoleStyle, ExitCode, as_command, escape

from xtr_ai.exception import PlatformUnavailableError
from xtr_ai.platform_registry_interface import PlatformRegistryInterface

from ._registry import AI_COMMANDS

__all__ = ["PlatformInvokeCommand"]


@as_command("ai:platform:invoke", registry=AI_COMMANDS)
@final
class PlatformInvokeCommand:
    """Send one message to a model of a platform; print the answer and the usage."""

    __slots__ = ("_registry",)

    def __init__(self, registry: PlatformRegistryInterface) -> None:
        """Reach the platforms through ``registry``."""
        self._registry = registry

    async def __call__(self, io: ConsoleStyle, platform: str, model: str, message: str) -> int:
        """Ask ``model`` of ``platform`` one question.

        Args:
            io: Where the command writes.
            platform: The configured platform.
            model: The model's name on that platform.
            message: What to send.
        """
        try:
            built = (await self._registry.get(platform)).model(model)
            # A single request reads no settings from the model itself, unlike an agent run:
            # the platform's defaults are handed over here.
            response = await model_request(
                built, [ModelRequest.user_text_prompt(message)], model_settings=built.settings
            )
        except (PlatformUnavailableError, ModelAPIError) as error:
            io.error(escape(str(error)))
            return ExitCode.FAILURE
        text = "".join(part.content for part in response.parts if isinstance(part, TextPart))
        io.text(escape(text))
        usage = response.usage
        io.note(
            f"{usage.input_tokens} input tokens, {usage.output_tokens} output tokens, "
            f"finish reason: {escape(str(response.finish_reason))}",
        )
        return ExitCode.SUCCESS
