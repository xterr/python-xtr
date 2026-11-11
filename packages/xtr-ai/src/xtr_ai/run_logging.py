"""What an agent run did, logged without what was said."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import anyio
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.exceptions import RunCancelled
from typing_extensions import override

if TYPE_CHECKING:
    from pydantic_ai import RunContext
    from pydantic_ai.messages import ModelResponse
    from pydantic_ai.models import ModelRequestContext
    from pydantic_ai.run import AgentRunResult
    from xtr_logging_contracts import LoggerInterface

    from xtr_ai.platform_registry_interface import PlatformRegistryInterface

__all__ = ["RunLogging"]


# Not final: a final dataclass with a defaulted field must initialise the keyword-only marker
# pydantic-ai's capability base declares, which only that base's own dataclass machinery sets.
@dataclass
class RunLogging(AbstractCapability[Any]):
    """Logs each model response and each run's end, with counts and ids only.

    Every record carries the agent, the run and conversation ids and the model;
    a response adds its token counts and finish reason, a run's end its totals,
    a failure the error's type. No prompt, instruction, message part or output
    is ever logged, nor an error's message, which may quote them.

    Pass ``registry`` to name the platform that served each response.
    """

    logger: LoggerInterface
    registry: PlatformRegistryInterface | None = field(default=None)

    @override
    async def after_model_request(
        self,
        ctx: RunContext[Any],
        *,
        request_context: ModelRequestContext,
        response: ModelResponse,
    ) -> ModelResponse:
        del request_context
        self.logger.debug(
            "The model answered.",
            {
                **self._identity(ctx),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "finish_reason": response.finish_reason,
            },
        )
        return response

    @override
    async def after_run(
        self,
        ctx: RunContext[Any],
        *,
        result: AgentRunResult[Any],
    ) -> AgentRunResult[Any]:
        usage = result.usage
        self.logger.info(
            "The agent run finished.",
            {
                **self._identity(ctx),
                "requests": usage.requests,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
            },
        )
        return result

    @override
    async def on_run_error(
        self,
        ctx: RunContext[Any],
        *,
        error: BaseException,
    ) -> AgentRunResult[Any]:
        context = {
            **self._identity(ctx),
            "requests": ctx.usage.requests,
            "error": type(error).__qualname__,
        }
        if isinstance(error, (RunCancelled, anyio.get_cancelled_exc_class())):
            # Asked for, or a deadline reached: an outcome, not a fault.
            self.logger.info("The agent run was cancelled.", context)
        else:
            self.logger.warning("The agent run failed.", context)
        raise error

    @classmethod
    @override
    def get_serialization_name(cls) -> str | None:
        # Built in code around an injected logger; it has no declarative form.
        return None

    def _identity(self, ctx: RunContext[Any]) -> dict[str, str | None]:
        model = ctx.model
        platform = self.registry.platform_of(model) if self.registry is not None else None
        return {
            "agent": ctx.agent.name if ctx.agent is not None else None,
            "platform": platform,
            "model": model.model_name,
            "run_id": ctx.run_id,
            "conversation_id": ctx.conversation_id,
        }
