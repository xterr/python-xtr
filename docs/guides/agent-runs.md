# Stop an agent run

An agent run can take minutes and spend money at each step. The place of the run
decides how it stops. A run in its own web request stops when the client goes
away. A run in a background job stops when the job tells it to stop. The
`StopWhen` capability does that for both: before each step of the run, it asks
the application a question. When the answer is yes, it cancels the run.

The `shop` application in this guide has two agents. The `assistant` answers in
a web request. The `researcher` writes long reports in a worker, behind the
message bus.

## Before you start

1. Create the application with `uvx xtr-cli new shop --webapp`. The template
   adds `xtr-orm` and `xtr-messenger`.
2. Add the package with `uv run xtr-recipes recipes:add "xtr-ai[openai]"`. The
   recipe lists `AiBundle` and writes `src/shop/config/packages/ai.py`.
3. Add the database transport with `uv run xtr-recipes recipes:add "xtr-messenger[orm]"`.
4. Put the values of this machine in `.env.local`:

   ```sh
   DATABASE_URL=sqlite+aiosqlite:///var/shop.sqlite
   MESSENGER_DSN=orm://default
   OPENAI_API_KEY=sk-...
   ```

5. Run `uv run shop debug:bundles`. The output names `ai`, `orm` and `messenger`
   as `active`.

> [!WARNING]
> Keep the key out of `.env`, because git tracks that file. `.gitignore`
> excludes `.env.local`.

## Configure the agents

1. Open `src/shop/config/packages/ai.py`.
2. Declare the platform and the two agents:

   ```python
   """The language-model platforms and the agents built on them."""

   from __future__ import annotations

   from xtr_ai.bundle import AgentConfig, AiConfig, PlatformConfig
   from xtr_dependency_injection import configure, env

   __all__ = ["ai"]


   @configure
   def ai() -> AiConfig:
       """One platform, and the two agents of the application."""
       return AiConfig(
           platforms={
               "openai": PlatformConfig(provider="openai", api_key=env("OPENAI_API_KEY")),
           },
           agents={
               "assistant": AgentConfig(
                   platform="openai",
                   model="gpt-5-mini",
                   instructions="Answer briefly.",
               ),
               "researcher": AgentConfig(
                   platform="openai",
                   model="gpt-5",
                   instructions="Search the library as often as you need, then write a report.",
               ),
           },
       )
   ```

3. Run `uv run shop debug:ai`. The output lists the `openai` platform and the
   two agents.

## Add the capability

`StopWhen` is a capability of the application. It holds no state, and it runs
no task of its own. pydantic-ai calls it before each model request and before
each tool call.

1. Create `src/shop/ai/__init__.py` with a docstring.
2. Create `src/shop/ai/stop_when.py`:

   ```python
   """Stop an agent run at its next step, when the application says so."""

   from __future__ import annotations

   from collections.abc import Awaitable, Callable
   from dataclasses import dataclass

   from pydantic_ai import RunContext
   from pydantic_ai.capabilities import AbstractCapability, ValidatedToolArgs
   from pydantic_ai.messages import ToolCallPart
   from pydantic_ai.models import ModelRequestContext
   from pydantic_ai.tools import ToolDefinition
   from typing_extensions import override

   __all__ = ["StopWhen"]


   @dataclass
   class StopWhen(AbstractCapability[object]):
       """Cancel the run before its next model request or tool call, once ``should_stop`` is true.

       A model response that streams now ends before the run stops.
       """

       should_stop: Callable[[], Awaitable[bool]]

       @override
       async def before_model_request(
           self, ctx: RunContext[object], request_context: ModelRequestContext
       ) -> ModelRequestContext:
           """Cancel the run before it asks the model again."""
           if await self.should_stop():
               ctx.cancel()
           return request_context

       @override
       async def before_tool_execute(
           self,
           ctx: RunContext[object],
           *,
           call: ToolCallPart,
           tool_def: ToolDefinition,
           args: ValidatedToolArgs,
       ) -> ValidatedToolArgs:
           """Cancel the run before it calls a tool."""
           del call, tool_def
           if await self.should_stop():
               ctx.cancel()
           return args

       @classmethod
       @override
       def get_serialization_name(cls) -> str | None:
           """Keep the capability out of the declarative agent definitions."""
           return None
   ```

3. Give the capability to a run, not to the agent: `agent.run(prompt, capabilities=[stop])`.
   Each run then asks its own question.

A cancelled run raises `RunCancelled`. The messages that the run completed stay
in its history.

## Stop a run in a web request

A run in a web request has two forms. A streamed run stops by itself. A run
that answers in one piece needs `StopWhen`.

1. Open `src/shop/web/routes.py`.
2. Add the imports and the type of the agent:

   ```python
   from collections.abc import AsyncIterator
   from typing import Annotated

   from fastapi import APIRouter, Request, Response
   from fastapi.responses import StreamingResponse
   from pydantic_ai.agent import AbstractAgent
   from pydantic_ai.exceptions import RunCancelled
   from xtr_dependency_injection import Target

   from shop.ai.stop_when import StopWhen

   Assistant = Annotated[AbstractAgent, Target("assistant")]
   ```

3. Add a route that streams the answer:

   ```python
   @router.get("/ask")
   async def ask(question: str, assistant: Assistant) -> StreamingResponse:
       """Stream the answer; the run stops when the client goes away."""

       async def answer() -> AsyncIterator[str]:
           async with assistant.run_stream(question) as result:
               async for text in result.stream_text(delta=True):
                   yield text

       return StreamingResponse(answer(), media_type="text/plain")
   ```

   When the client goes away, the server cancels the stream. pydantic-ai then
   stops the run and closes the stream of the model.
4. Add a route that answers in one piece:

   ```python
   @router.get("/summary")
   async def summary(question: str, request: Request, assistant: Assistant) -> Response:
       """Answer in one piece; stop the run at its next step if the client goes away."""
       stop = StopWhen(request.is_disconnected)
       try:
           result = await assistant.run(question, capabilities=[stop])
       except RunCancelled:
           return Response(status_code=499)
       return Response(str(result.output), media_type="text/plain")
   ```

   The server does not cancel this route when the client goes away. `StopWhen`
   asks `request.is_disconnected` before each step, and stops the run.
5. Serve the application with `uv run shop-web`.
6. Send `curl --max-time 2 "localhost:8000/summary?question=Explain+anemia"`. Curl
   stops after 2 seconds, and the run stops at its next step.

## Stop a run in a background job

A background job runs in a worker, which can be on another server. The web
request that asks to stop the job cannot reach the run. The job must be a row in
the database: the request writes a flag on the row, and `StopWhen` reads it.

### Store the job

1. Create `src/shop/research/__init__.py` with a docstring.
2. Create `src/shop/research/research_job.py`:

   ```python
   """A research job, as one row of the ``research_job`` table."""

   from __future__ import annotations

   from enum import StrEnum
   from typing import final

   from advanced_alchemy.base import UUIDAuditBase
   from sqlalchemy import String, Text
   from sqlalchemy.orm import Mapped, mapped_column

   __all__ = ["JobStatus", "ResearchJob"]


   class JobStatus(StrEnum):
       """Where a research job stands."""

       QUEUED = "queued"
       RUNNING = "running"
       DONE = "done"
       CANCELLED = "cancelled"
       FAILED = "failed"


   @final
   class ResearchJob(UUIDAuditBase):
       """One research job: what to research, where it stands, and what it found."""

       __tablename__ = "research_job"

       prompt: Mapped[str] = mapped_column(Text)
       status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED)
       cancel_requested: Mapped[bool] = mapped_column(default=False)
       result: Mapped[str | None] = mapped_column(Text, default=None)
   ```

3. Create `src/shop/research/job_store.py`:

   ```python
   """Research jobs, read and written in short transactions of their own."""

   from __future__ import annotations

   from typing import cast, final
   from uuid import UUID

   from sqlalchemy import CursorResult, select, update
   from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
   from xtr_dependency_injection import Injected, as_service

   from shop.research.research_job import JobStatus, ResearchJob

   __all__ = ["JobStore"]

   _OPEN = (JobStatus.QUEUED, JobStatus.RUNNING)


   @final
   @as_service
   class JobStore:
       """Each call opens its own session, so it sees what another server committed."""

       def __init__(self, sessions: Injected[async_sessionmaker[AsyncSession]]) -> None:
           """Open sessions with ``sessions``."""
           self._sessions = sessions

       async def create(self, prompt: str) -> UUID:
           """Store a new job; answer its id."""
           async with self._sessions.begin() as session:
               job = ResearchJob(prompt=prompt)
               session.add(job)
               await session.flush()
               return job.id

       async def get(self, job_id: UUID) -> ResearchJob | None:
           """Answer the job, or ``None`` when no job has that id."""
           async with self._sessions() as session:
               return await session.get(ResearchJob, job_id)

       async def start(self, job_id: UUID) -> bool:
           """Mark the job running; answer false when it already ended."""
           return await self._update_open(job_id, status=JobStatus.RUNNING)

       async def request_cancel(self, job_id: UUID) -> bool:
           """Set the flag; answer false when the job already ended."""
           return await self._update_open(job_id, cancel_requested=True)

       async def cancel_requested(self, job_id: UUID) -> bool:
           """Answer whether somebody asked the job to stop."""
           async with self._sessions() as session:
               flag = await session.scalar(
                   select(ResearchJob.cancel_requested).where(ResearchJob.id == job_id)
               )
               return bool(flag)

       async def finish(self, job_id: UUID, status: JobStatus, result: str | None = None) -> None:
           """Record how the job ended."""
           async with self._sessions.begin() as session:
               _ = await session.execute(
                   update(ResearchJob)
                   .where(ResearchJob.id == job_id)
                   .values(status=status, result=result)
               )

       async def _update_open(self, job_id: UUID, **values: object) -> bool:
           async with self._sessions.begin() as session:
               result = cast(
                   "CursorResult[tuple[()]]",
                   await session.execute(
                       update(ResearchJob)
                       .where(ResearchJob.id == job_id, ResearchJob.status.in_(_OPEN))
                       .values(**values)
                   ),
               )
               return result.rowcount == 1
   ```

4. Write the migration with `uv run shop orm:migrations:diff --message "research jobs"`.
   The revision creates the `research_job` table and the table of the messages.
5. Apply it with `uv run shop orm:migrations:migrate`.

> [!WARNING]
> Read the flag in a session of its own, as `JobStore` does. Do not read it on the
> session of the handler. That session holds one transaction for the whole message.
> On MySQL, that transaction never sees a flag that another server writes later.

### Send the job to a worker

1. Create `src/shop/research/message.py`:

   ```python
   """The message that starts a research job on a worker."""

   from __future__ import annotations

   from dataclasses import dataclass
   from uuid import UUID

   from xtr_messenger import as_message

   __all__ = ["RunResearch"]


   @as_message(name="shop.run_research.v1")
   @dataclass(frozen=True, slots=True)
   class RunResearch:
       """Run the research job ``job_id``."""

       job_id: UUID
   ```

2. Open `src/shop/config/packages/messenger.py`.
3. Route the message to a `research` transport:

   ```python
   @configure
   def messenger() -> MessageBusConfig:
       """One transport, its broker read from ``MESSENGER_DSN``."""
       return MessageBusConfig(
           transports={"research": TransportConfig(env("MESSENGER_DSN"))},
           routing={RunResearch: "research"},
       )
   ```

4. Add `from shop.research.message import RunResearch` to the imports of the file.

### Give the researcher a tool

1. Create `src/shop/research/library.py`:

   ```python
   """The tools the researcher calls."""

   from __future__ import annotations

   from typing import final

   from xtr_ai import as_tool

   __all__ = ["Library"]


   @final
   class Library:
       """The clinic's library, searched by the researcher."""

       @as_tool(agents=("researcher",))
       async def search(self, query: str) -> str:
           """Search the clinic's library for a query."""
           return f"three articles about {query}"
   ```

   The researcher now calls `search` many times in one run. `StopWhen` asks its
   question before each of those calls.

### Run the job in the worker

1. Create `src/shop/research/handler.py`:

   ```python
   """The worker's side of a research job."""

   from __future__ import annotations

   from typing import Annotated

   from pydantic_ai.agent import AbstractAgent
   from pydantic_ai.exceptions import RunCancelled
   from xtr_dependency_injection import Injected, Target
   from xtr_messenger import as_message_handler

   from shop.ai.stop_when import StopWhen
   from shop.research.job_store import JobStore
   from shop.research.message import RunResearch
   from shop.research.research_job import JobStatus

   __all__ = ["run_research"]


   @as_message_handler(RunResearch)
   async def run_research(
       message: RunResearch,
       jobs: Injected[JobStore],
       researcher: Annotated[AbstractAgent, Target("researcher")],
   ) -> None:
       """Run the researcher until it answers, or until the job is cancelled."""
       job = await jobs.get(message.job_id)
       if job is None or not await jobs.start(job.id):
           return  # a delivery of a job that already ended
       stop = StopWhen(lambda: jobs.cancel_requested(job.id))
       try:
           result = await researcher.run(job.prompt, capabilities=[stop])
       except RunCancelled:
           await jobs.finish(job.id, JobStatus.CANCELLED)
           return
       except Exception:
           await jobs.finish(job.id, JobStatus.FAILED)
           raise
       await jobs.finish(job.id, JobStatus.DONE, str(result.output))
   ```

2. Keep the first check of the handler. The transport sends a message again
   after a worker stops in the middle of a job. A job that ended stays ended.
   A job that is still `running` starts again from its prompt.

### Start, follow and stop the job

1. Add the imports to `src/shop/web/routes.py`:

   ```python
   from uuid import UUID

   from fastapi import HTTPException
   from xtr_dependency_injection import Injected
   from xtr_messenger import MessageBusInterface

   from shop.research.job_store import JobStore
   from shop.research.message import RunResearch
   ```

2. Add the three routes of a job:

   ```python
   @router.post("/research", status_code=202)
   async def start_research(
       prompt: str, jobs: Injected[JobStore], bus: Injected[MessageBusInterface]
   ) -> dict[str, str]:
       """Create the job, and hand it to a worker."""
       job_id = await jobs.create(prompt)
       _ = await bus.dispatch(RunResearch(job_id=job_id))
       return {"job_id": str(job_id)}


   @router.post("/research/{job_id}/cancel", status_code=202)
   async def cancel_research(job_id: UUID, jobs: Injected[JobStore]) -> dict[str, str]:
       """Ask the worker to stop; it stops at the run's next step."""
       if not await jobs.request_cancel(job_id):
           raise HTTPException(status_code=409, detail="The job already ended.")
       return {"status": "cancelling"}


   @router.get("/research/{job_id}")
   async def research_status(job_id: UUID, jobs: Injected[JobStore]) -> dict[str, str | None]:
       """Answer where the job stands."""
       job = await jobs.get(job_id)
       if job is None:
           raise HTTPException(status_code=404)
       return {"status": job.status, "result": job.result}
   ```

### Try it

1. Serve the application with `uv run shop-web`.
2. In a second terminal, run the worker with `uv run shop messenger:consume research`.
3. Start a job:

   ```sh
   curl -s -X POST "localhost:8000/research?prompt=rare+kidney+disorders"
   ```

   The answer gives the id of the job, for example
   `{"job_id":"3a2f2efb-6663-415a-92a5-42bec02a101f"}`.
4. Ask for the state with `curl -s localhost:8000/research/<job_id>`. The answer
   is `{"status":"running","result":null}`.
5. Stop the job with `curl -s -X POST localhost:8000/research/<job_id>/cancel`.
   The answer is `{"status":"cancelling"}`.
6. Ask for the state again. The answer is `{"status":"cancelled","result":null}`.
7. Stop the job again. The answer has the status code 409, because the job ended.

## When the run stops

| The run is | It stops |
|---|---|
| Streamed in a web request | When the client goes away, in the middle of the stream |
| In one piece in a web request | Before its next model request or tool call |
| In a background job | Before its next model request or tool call |

A model request that has started always ends before the run stops. If this
delay is too long for a job, send the signal to the worker instead. For example,
use `LISTEN` and `NOTIFY` of PostgreSQL. `StopWhen` then reads a value in memory.

## Next step

- [Send and handle messages](messages.md) describes the transports and the
  worker.
- [Test an application](testing.md) runs a handler with no broker.
- [xtr-ai](https://github.com/xterr/python-xtr/tree/main/packages/xtr-ai)
  describes the platforms, the agents and the conversation stores.
