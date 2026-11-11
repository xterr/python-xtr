# xtr-ai-orm-conversation-store

Agent conversations kept in two tables on an [xtr-orm](../xtr-orm) connection, for
[xtr-ai](../xtr-ai).

## Install

```sh
uv add "xtr-ai[orm]"
```

The `orm` extra installs this package.

## Use

`OrmConversationStore` is a pydantic-ai `ConversationStore`. Give it the connection's primary
engine:

```python
from pydantic_ai.conversation import Conversation

from xtr_ai_orm_conversation_store import OrmConversationStore

store = OrmConversationStore(engine)
conversation = await store.load(conversation_id) or Conversation(conversation_id=conversation_id)
result = await agent.run(prompt, conversation=conversation)
await store.save(result)
```

In an application, configure it in xtr-ai instead, as
`conversation_stores={"default": OrmConversationStoreConfig(connection="default")}`, and inject
`ConversationStore`. See xtr-ai's [Use in an application](../xtr-ai#use-in-an-application).

## Tables

| Table | Holds |
|---|---|
| `ai_conversation` | One row per conversation: where its history ends, usage, pending tool calls, scope, branches, fork origin, revision |
| `ai_conversation_entry` | One row per message, pointing at the one before it; shared by a conversation and its forks |

`table_prefix` changes `ai_`. `ConversationMappingDriver` adds the tables to a connection's
definitions, so `orm:migrations:diff` writes them. xtr-ai registers it when the store is
configured.

## Behaviour

- **Own transactions.** Every call runs in a short transaction of its own and commits before it
  returns. A store never joins the caller's unit of work.
  - A long model call holds no database connection.
  - Rolling back the caller's work never undoes a saved turn.
  - A conversation cannot be saved atomically with the application's own rows.
- **Conflicts.** A record and the messages it adds are written in one transaction. A save over a
  newer revision raises `ConversationConflict` and leaves neither behind.
- **History.** A conversation's history is read in one recursive query.
- **Deleting.** Deleting a conversation deletes the messages only it reaches. Messages a fork,
  or its origin, still reaches stay until the last of them is deleted.
  - A fork saved while its origin is being deleted can lose the messages it shares with it,
    except on SQLite, where writes take turns. Don't fork a conversation you are deleting.
- **Databases.** It runs on PostgreSQL, MySQL 8 and SQLite, through their async drivers.

## Development

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT
