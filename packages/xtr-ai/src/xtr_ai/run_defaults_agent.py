"""An agent whose runs get default usage limits and a default timeout."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, final

from pydantic_ai.agent import AbstractAgent, WrapperAgent
from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pydantic_ai.run import AgentRun
    from pydantic_ai.usage import UsageLimits

__all__ = ["RunDefaultsAgent"]


@final
class RunDefaultsAgent(WrapperAgent[Any, Any]):
    """Runs ``wrapped`` with ``usage_limits`` and ``timeout`` unless a call passes its own.

    pydantic-ai takes both per run only. This wrapper adds no method and changes
    nothing else: ``run``, ``run_sync``, ``run_stream`` and ``iter`` all reach
    the wrapped agent through ``iter``, where a default fills an argument the
    caller left out or passed as ``None``. Being a wrapper, it is an
    ``AbstractAgent`` but not an ``Agent``.
    """

    def __init__(
        self,
        wrapped: AbstractAgent[Any, Any],
        *,
        usage_limits: UsageLimits | None = None,
        timeout: float | None = None,
    ) -> None:
        """Wrap ``wrapped`` with the defaults its runs get."""
        super().__init__(wrapped)
        self.default_usage_limits: UsageLimits | None = usage_limits
        self.default_timeout: float | None = timeout

    @override
    @asynccontextmanager
    # Forwards every argument unchanged: restating pydantic-ai's two dozen keywords would drift
    # with each release.
    async def iter(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> AsyncGenerator[AgentRun[Any, Any]]:
        if kwargs.get("usage_limits") is None and self.default_usage_limits is not None:
            kwargs["usage_limits"] = self.default_usage_limits
        if kwargs.get("timeout") is None and self.default_timeout is not None:
            kwargs["timeout"] = self.default_timeout
        async with self.wrapped.iter(*args, **kwargs) as run:
            yield run
