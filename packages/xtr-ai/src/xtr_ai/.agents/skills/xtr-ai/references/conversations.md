# Conversations, and stopping a run

## Conversation stores

The port is pydantic-ai's `ConversationStore`. A store is named; `"default"` is also injected
without a name.

| Config | Store | Keeps |
|---|---|---|
| `InMemoryConversationStoreConfig()` | pydantic-ai's `InMemoryConversationStore` | this process |
| `OrmConversationStoreConfig(connection="default", table_prefix="ai_")` | `OrmConversationStore` | `ai_conversation`, `ai_conversation_entry` |
| `ServiceConversationStoreConfig(service=MyStore)` | the application's own | its own |

- **Transactions.** The orm store writes in short transactions of its own, on the connection's
  primary engine, and commits before it returns. It never joins the caller's unit of work.
- **Conflicts.** A save over a newer revision raises pydantic-ai's `ConversationConflict`: load
  the conversation again and retry. Two runs of one conversation cannot both save.
- **Deleting.** `delete` removes every message only that conversation reaches. Messages a fork
  shares stay until the last conversation reaching them is deleted.
- **Migrations.** `orm:migrations:diff` writes the tables.

## Stopping a run

xtr-ai tracks no runs. Where the run is decides how it stops.

- **Streamed in its own request**, as an interactive chat is: it stops when the client goes away.
  The web framework cancels the request's task, and pydantic-ai cancels the run and closes the
  model's stream. Nothing to write.
- **In a background job**, dispatched through the message bus: the job is the application's own
  entity. It holds the status, a `cancel_requested` flag, progress and the result. The Stop
  request, on any server, sets the flag. The worker running the agent checks the flag at each of
  the run's steps with a capability, and calls `ctx.cancel()`:

```python
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models import ModelRequestContext
from pydantic_ai.tools import ToolDefinition


@dataclass
class StopWhen(AbstractCapability[Any]):
    """Cancels the run at its next step once ``should_stop`` answers true."""

    should_stop: Callable[[], Awaitable[bool]]

    async def before_model_request(
        self, ctx: RunContext[Any], request_context: ModelRequestContext
    ) -> ModelRequestContext:
        if await self.should_stop():
            ctx.cancel()
        return request_context

    async def before_tool_execute(
        self, ctx: RunContext[Any], *, call: ToolCallPart, tool_def: ToolDefinition, args: Any
    ) -> Any:
        if await self.should_stop():
            ctx.cancel()
        return args

    @classmethod
    def get_serialization_name(cls) -> str | None:
        return None
```

In the message handler:

```python
stop = StopWhen(lambda: jobs.cancel_requested(job_id))
try:
    result = await agent.run(prompt, capabilities=[stop])
except RunCancelled:
    ...  # mark the job cancelled; keep or drop its partial findings
```

- **Read the flag in a session of its own**, never on the handler's: that session is one
  transaction for the whole message, and on MySQL it never sees a flag another server writes.
- **Latency.** A cancel takes effect at the next step, so a model response already streaming
  finishes first. Push the signal instead (PostgreSQL `LISTEN/NOTIFY`, Redis) only if that is too
  slow.
- **Child agents.** `StopWhen` stops only the run it is given to: give it to every run of the
  job.
- **A run that answers in one piece in a web request** is not cancelled when the client goes
  away. Give it `StopWhen(request.is_disconnected)`. A streamed run needs nothing.
- **Redelivery.** After a worker crash the bus delivers the job again. The handler reads the
  job's status and resumes from the stored conversation, or starts over.
- **One job at a time.** A unique constraint or a workflow guard on the job entity.
