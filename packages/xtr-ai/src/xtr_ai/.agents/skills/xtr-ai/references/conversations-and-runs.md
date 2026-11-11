# Conversations and runs

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
  the conversation again and retry.
- **Deleting.** `delete` removes every message only that conversation reaches. Messages a fork
  shares stay until the last conversation reaching them is deleted.
- **Migrations.** `orm:migrations:diff` writes the tables.

## Run control

| Config | Run control | Reach |
|---|---|---|
| `InMemoryRunControlConfig()` | `InMemoryRunControl` | one process |
| `OrmRunControlConfig(connection="default", table_prefix="ai_")` | `OrmRunControl` | every process on the database |
| `ServiceRunControlConfig(service=MyRunControl)` | the application's own | its own |

Every config takes `cancel_poll_interval` (1 second), `heartbeat_interval` (10 seconds) and
`stale_after` (60 seconds).

- **`start`** records a running run, refusing a second top-level run of one conversation with
  `RunInProgressError`. A run given a `parent_run_id` is exempt.
- **`watch`** cancels the token when a cancellation is asked for, and on the way out writes
  finished, cancelled or failed. The write is shielded, and the first state written wins.
- **`get`** returns `RunStatus`: state, usage, metadata (check ownership there) and times.
- **`request_cancel`** says whether a running run was flagged.
- **Crashes.** A run silent for `stale_after` (its process died) is marked failed by the next
  run of its conversation.

A backend of your own subclasses `AbstractRunControl` and implements `_insert`, `_read`, `_poll`,
`_flag_cancel` and `_finish`; `RunControlContract` checks it.
