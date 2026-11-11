# xtr-ai-orm-run-control

Agent runs tracked in a table on an [xtr-orm](../xtr-orm) connection, so any process reads them
and cancels them, for [xtr-ai](../xtr-ai).

## Install

```sh
uv add "xtr-ai[orm]"
```

The `orm` extra installs this package and
[xtr-ai-orm-conversation-store](../xtr-ai-orm-conversation-store).

## Use

`OrmRunControl` is an xtr-ai `RunControlInterface`. Give it the connection's primary engine:

```python
from pydantic_ai import CancellationToken

from xtr_ai_orm_run_control import OrmRunControl

run_control = OrmRunControl(engine)
await run_control.start(run_id, agent="chat", conversation_id=conversation_id)
token = CancellationToken()
async with run_control.watch(run_id, token) as watched:
    result = await agent.run(prompt, run_id=run_id, cancellation_token=token)
    watched.record_usage(result.usage)

# from any process on the same database
await run_control.request_cancel(run_id)
```

In an application, configure it in xtr-ai instead, as
`runs=OrmRunControlConfig(connection="default")`, and inject `RunControlInterface`. See
xtr-ai's [Use in an application](../xtr-ai#use-in-an-application).

## Table

`ai_run` holds one row per run: its agent, its conversation and parent, its state, whether
cancellation was asked for, its usage and metadata, and its start, heartbeat and end times.
`table_prefix` changes `ai_`. `RunMappingDriver` adds the table to a connection's definitions,
so `orm:migrations:diff` writes it.

## Behaviour

- **Own transactions.** Every call runs in a short transaction of its own and commits before it
  returns.
  - A cancellation asked for in one process is what the watching process reads next.
  - A run's end is recorded even when the caller's own work rolls back.
- **One run per conversation.** A unique index on `active_key` allows one top-level run in
  progress per conversation. `active_key` holds the conversation of a running top-level run, and
  is empty otherwise. This works on PostgreSQL, MySQL and SQLite, with no partial index.
- **Crashes.** A watched run writes its heartbeat. One silent for `stale_after` (its process
  died) is marked failed by the next run of its conversation.
- **Timings.** `cancel_poll_interval`, `heartbeat_interval` and `stale_after` are xtr-ai's.

## Development

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT
