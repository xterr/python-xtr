# xtr-ai

Named language-model platforms and agents, built on
[pydantic-ai](https://ai.pydantic.dev), with conversation stores and run control an application
already has the infrastructure for.

## Why?

pydantic-ai already does what an agent needs: providers and models, tools and toolsets,
capabilities, MCP, conversations and their stores. What every application still writes on top of
it is the same layer: where the keys come from, which model an agent uses in which environment,
how an agent reaches the application's services, where conversations are kept, and how a run in
one process is stopped from another. This package is that layer, and nothing more.

- **Named platforms.** A platform is a provider with its key and endpoint. An agent's model id is
  `<platform>:<model>`, so moving an agent to another provider, region or a local server is a
  configuration change.
- **Built when used.** No provider SDK is imported and no client is built while the application
  starts, so the console runs without any key.
- **pydantic-ai's own types.** An application gets an `AbstractAgent` and a `ConversationStore`
  and can still use every part of pydantic-ai directly.
- **Run control.** What pydantic-ai has no answer for: a run's status, and cancelling it, from
  another process.

## Install

```sh
uv add xtr-ai                # the core
uv add "xtr-ai[openai]"      # with a provider: openai, anthropic, google, bedrock, mistral, groq, openrouter
uv add "xtr-ai[orm]"         # conversations and run control kept in the database
```

The provider extras are pydantic-ai's own, under the same names, plus `mcp` and `ag-ui`.

## Quick start

Everything works without a container:

```python
from pydantic_ai import Agent
from pydantic_ai.capabilities import ResolveModelId

from xtr_ai import Platform, PlatformRegistry

registry = PlatformRegistry.of(
    Platform("openai", "openai", api_key="sk-..."),
    Platform("local", "openai", base_url="http://localhost:11434/v1", api_key="local"),
)
agent = Agent("openai:gpt-5-mini", capabilities=[ResolveModelId(registry.resolve)])

result = await agent.run("Hello")
result = await agent.run("Hello again", model="local:llama-3.3-70b")  # another platform, one run
```

## Platforms

A `Platform` names a provider and how to reach it: `Platform(name, provider, *, api_key=,
base_url=, options=, model_settings=)`.

- **Any pydantic-ai provider.** `provider` is any name pydantic-ai knows (`openai`, `anthropic`,
  `azure`, `bedrock`, `google`, `mistral`, `groq`, `openrouter`, `ollama`, …). A provider added to
  pydantic-ai needs nothing here.
- **Offline.** `test` builds pydantic-ai's `TestModel` from `options`, and `function` builds a
  `FunctionModel` from `options["function"]` and/or `options["stream_function"]`. Neither needs a
  key.
- **Options.** `options` are the provider's other constructor keywords (`api_version`, `region`,
  `project`, …), passed unchanged.
- **OpenAI-compatible servers.** A local server, such as Ollama or vLLM, is `provider="openai"`
  with its `base_url`. The OpenAI SDK refuses an empty key, so give it any non-empty one.
- **Defaults.** `model_settings` are defaults every model of the platform carries, beneath the
  agent's and the run's settings.
- **Many of one kind.** Two Azure deployments are two platforms.
- **Built once.** The provider is built the first time a model is asked for, then shared by
  every model of that platform.
- **Errors.** A missing extra, an unknown provider or a keyword the provider refuses raises
  `PlatformUnavailableError`, naming the platform but never a key's value.
- **HTTP.** The provider SDKs own their HTTP clients. `PlatformRegistry.aclose()`, and the
  bundle at shutdown, close those it opened.

`PlatformRegistry.resolve` is the resolver for pydantic-ai's `ResolveModelId`: an id whose prefix
names a platform resolves there, and any other is left to pydantic-ai.

Code depending on a platform or the registry takes `PlatformInterface` or
`PlatformRegistryInterface`. A platform of your own implements `PlatformInterface`: a name, a
provider, `model(name)`, `built(model)` and `aclose()`. Examples are models from a client you
already hold, a gateway, or a recorded double. It goes wherever a `Platform` does, including
`PlatformRegistry.of(...)`.

## Agents

With the bundle, an agent is configured, and injected by name (see
[Kernel / bundle](#kernel--bundle)). Without it, any pydantic-ai agent works with the pieces
below:

| Piece | What it does |
|---|---|
| `RunDefaultsAgent(agent, usage_limits=, timeout=)` | Gives every run defaults pydantic-ai only takes per run; a call passing its own wins. An `AbstractAgent`, not an `Agent` |
| `RunClock(clock)` | Measures a run's `timeout` against an xtr-clock `ClockInterface`. Message timestamps still come from the system clock |
| `RunLogging(logger, registry)` | Logs each response and each run's end with ids, token counts and finish reasons: never a prompt, an instruction or an output |
| `agent_toolset(agent, name=)` | Another agent as a tool. Its usage counts toward the caller's |

## Tools

Mark a service's methods with `@as_tool`. With the bundle they become tools of the agents named,
called on the service the container builds:

```python
from xtr_ai import as_tool


class Weather:
    def __init__(self, client: WeatherClient) -> None:
        self._client = client

    @as_tool(agents=("chat",))
    async def forecast(self, city: str) -> str:
        """Tomorrow's forecast for a city."""
        return await self._client.forecast(city)
```

The first parameter may be a pydantic-ai `RunContext`. Without the container, `service_toolset(
Weather(client), "chat")` returns the same toolset. A tool's service is built once and shared by
every run, so it must be a singleton. Per-run state belongs in the run's `deps`.

## Conversations

pydantic-ai's `ConversationStore` is the port: load a conversation, run, save the result.

```python
conversation = await store.load(conversation_id) or Conversation(conversation_id=conversation_id)
result = await agent.run(prompt, conversation=conversation)
await store.save(result)
```

| Store | Package | Keeps |
|---|---|---|
| pydantic-ai's `InMemoryConversationStore` | here | this process, until it stops |
| `OrmConversationStore` | [xtr-ai-orm-conversation-store](../xtr-ai-orm-conversation-store) | two tables on an xtr-orm connection |
| any `ConversationStore` | the application's | wherever it says |

Every store but the in-memory one writes in transactions of its own, never as part of the
caller's. A conversation cannot be saved atomically with the application's own rows.

## Run control

`RunControlInterface` covers what a run is doing now:

```python
from pydantic_ai import CancellationToken

await run_control.start(
    run_id, agent="chat", conversation_id=conversation_id, metadata={"user": user_id}
)
token = CancellationToken()
async with run_control.watch(run_id, token) as watched:
    result = await agent.run(
        prompt, run_id=run_id, conversation=conversation, cancellation_token=token
    )
    watched.record_usage(result.usage)

# from any process
await run_control.request_cancel(run_id)
status = await run_control.get(run_id)  # state, usage, metadata
```

- **One run per conversation.** A conversation has one top-level run in progress at a time;
  `start` raises `RunInProgressError` for a second. A run given a `parent_run_id` is exempt.
- **Cancelling.** `watch` reads the cancel flag every `cancel_poll_interval` and cancels the
  token. In the same process, `request_cancel` cancels it at once.
- **Ending.** On the way out, `watch` writes how the run ended: finished, cancelled
  (`RunCancelled` or task cancellation) or failed (any other error). The write is shielded from
  cancellation, and the first state written wins.
- **Crashes.** A watched run reports itself alive every `heartbeat_interval`. Once one has been
  silent for `stale_after` (its process died), the next run of its conversation marks it failed
  and starts.

| Run control | Package | Reach |
|---|---|---|
| `InMemoryRunControl` | here | one process |
| `OrmRunControl` | [xtr-ai-orm-run-control](../xtr-ai-orm-run-control) | every process on the database |
| any `RunControlInterface` | the application's | its own |

A backend of its own subclasses `AbstractRunControl`, implements five storage methods, and runs
`xtr_ai.testing.run_control_contract.RunControlContract` in its tests.

## Testing

- `override_agent_model(container, "chat", FunctionModel(...))` runs a configured agent on a
  scripted model inside an `async with` block, through pydantic-ai's `agent.override`.
- `test` and `function` platforms run with no key and no network.
- `InMemoryConversationStore` and `InMemoryRunControl` keep everything in the test's process.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes, and, read backwards, what removing it
undoes.

- **Install** — `uv add xtr-ai xtr-dependency-injection`: the bundle needs the container
  installed beside it, never as an extra. Add a provider extra, `uv add "xtr-ai[openai]"`, and
  `xtr-ai[orm]` to keep conversations and runs in the database.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* and *Configure* steps below:
  it lists `AiBundle` and writes `<app>/config/packages/ai.py` with an empty `AiConfig`. There
  is no environment to write and nothing to ignore.
- **Activate** — `AiBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
  from `xtr_ai.bundle`. To keep conversations or runs in the database, list `OrmBundle` too: it
  is never activated for you.
- **Brings along** — the clock, logging and console bundles, each when its package is installed:
  the clock measures run timeouts, logging adds the `ai` channel, and the console adds the
  commands.
- **Configure** — the recipe writes `<app>/config/packages/ai.py` declaring nothing. Platforms,
  agents, stores and run control go in that `@configure` function returning `AiConfig`. See
  [Kernel / bundle](#kernel--bundle).
- **Environment** — nothing required: the keys are the application's to name. A platform reads
  its key with `env(...)`, the first time an agent of it runs.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry. `uv run xtr-recipes recipes:remove xtr-ai` deletes
  `<app>/config/packages/ai.py`, or moves it aside to `ai.py.removed` if you edited it. Then
  `uv remove xtr-ai`. An orm store's tables stay until a migration drops them.
- **Check** — `debug:bundles` shows `ai` as `listed` and `active`, and `debug:ai` lists the
  platforms and agents.

## Kernel / bundle

```python
# app/config/bundles.py
from xtr_ai.bundle import AiBundle

BUNDLES = {AiBundle: {"all": True}}
```

```python
# app/config/packages/ai.py
from pydantic_ai.usage import UsageLimits
from xtr_dependency_injection import configure, env

from xtr_ai.bundle import (
    AgentConfig,
    AiConfig,
    ModelRef,
    OrmConversationStoreConfig,
    OrmRunControlConfig,
    PlatformConfig,
)


@configure
def ai() -> AiConfig:
    return AiConfig(
        platforms={
            "openai": PlatformConfig(provider="openai", api_key=env("OPENAI_API_KEY")),
            "local": PlatformConfig(
                provider="openai",
                base_url=env("LLM_BASE_URL"),
                api_key=env("LLM_API_KEY", default="local"),
            ),
            "azure_eu": PlatformConfig(
                provider="azure",
                api_key=env("AZURE_EU_KEY"),
                options={
                    "azure_endpoint": env("AZURE_EU_URL"),
                    "api_version": "2025-01-01-preview",
                },
            ),
        },
        agents={
            "chat": AgentConfig(
                platform=env("AI_CHAT_PLATFORM", default="openai"),
                model="gpt-5-mini",
                fallbacks=(ModelRef("local", "llama-3.3-70b"),),
                instructions_file="%kernel.project_dir%/prompts/chat.md",
                model_settings={"temperature": 0.2},
                deps_type=ChatDeps,
                capabilities=(ToolResultGuard, {"Thinking": {"effort": "low"}}),
                usage_limits=UsageLimits(request_limit=8),
                timeout=180,
            ),
        },
        conversation_stores={"default": OrmConversationStoreConfig(connection="default")},
        runs=OrmRunControlConfig(connection="default"),
    )
```

### Platforms and agents

- **Platform fields.** `PlatformConfig` takes `provider`, `api_key`, `base_url`, `options` and
  `model_settings`, as [Platforms](#platforms) describes. A key never shows in
  `debug:config` or `debug:ai`.
- **The model.** An agent's `platform` and `model` make its model id. Either may be `env(...)`,
  so the model is chosen per environment. A literal platform is checked at build; one from the
  environment is checked when the agent is first built, and an unknown one raises
  `PlatformUnavailableError`.
- **Fallbacks.** `fallbacks` become pydantic-ai's `ModelFallback`, tried in order when the model
  fails.
- **Instructions.** `instructions` holds them inline. `instructions_file` holds a path instead,
  read when the agent is first built.
- **Passed to pydantic-ai.** `model_settings`, `retries`, `end_strategy`, `tool_timeout`,
  `metadata`, `deps_type` and `output_type` go to pydantic-ai's `Agent.from_spec` as written.
- **Capabilities.** Each entry is pydantic-ai's declarative form (`"Thinking"`,
  `{"MCP": {"url": ..., "headers": {...}}}`), or a capability class the container builds with
  injection.
- **Toolsets.** `ToolsetRef(service=)` is a toolset class the container builds. `AgentToolRef(
  agent=, name=, description=)` calls another configured agent as a tool. Agents calling each
  other in a cycle are refused.
- **Run defaults.** `usage_limits` and `timeout` apply to every run unless the call passes its
  own. Such an agent is a `RunDefaultsAgent`.
- **Injection.** Inject one agent with `Annotated[AbstractAgent, Target("chat")]`, or all of them
  with `Mapping[Hashable, AbstractAgent]`. Agents are singletons, built on first injection.
- **Platforms in the container.** Each configured platform is registered under `PlatformInterface`,
  qualified by its name, as in `Annotated[PlatformInterface, Target("openai")]`. The registry is
  `PlatformRegistryInterface`.
- **Peer bundles.** With the clock bundle, every agent measures its timeout against
  `ClockInterface`. With the logging bundle, every agent logs on the `ai` channel.

### Conversation stores and run control

| Config | Registers |
|---|---|
| `InMemoryConversationStoreConfig()` | pydantic-ai's in-memory store |
| `OrmConversationStoreConfig(connection=, table_prefix=)` | `OrmConversationStore` on that connection's primary; needs `xtr-ai[orm]` |
| `ServiceConversationStoreConfig(service=)` | the application's own store, registered under that class |
| `InMemoryRunControlConfig(...)` | `InMemoryRunControl` |
| `OrmRunControlConfig(connection=, table_prefix=, ...)` | `OrmRunControl` on that connection's primary; needs `xtr-ai[orm]` |
| `ServiceRunControlConfig(service=)` | the application's own run control |

- **Injection.** A store is injected by name, `Annotated[ConversationStore, Target("archive")]`;
  `"default"` is also injected without one. Run control is `RunControlInterface`.
- **Off by default.** With `runs=None`, nothing is registered.
- **Timings.** Run control configs take `cancel_poll_interval`, `heartbeat_interval` and
  `stale_after`.
- **Migrations.** The orm adapters' tables join the connection's definitions, so
  `orm:migrations:diff` writes them.
- **A missing bridge.** An orm adapter whose bridge is not installed fails the build, naming
  `uv add "xtr-ai[orm]"`.
- **The orm bundle.** An orm adapter also fails the build when `OrmBundle` is not listed, naming
  it. Installing xtr-orm does not activate it.

### Commands

With the console bundle:

| Command | Does |
|---|---|
| `debug:ai` | Lists platforms (provider, whether a key is configured, never its value) and agents (model, fallbacks, capabilities, toolsets) |
| `ai:platform:invoke <platform> <model> <message>` | Sends one message and prints the answer and the usage |
| `ai:agent:call <agent>` | Talks to an agent; an empty line ends the conversation, held in memory |
| `ai:run:cancel <run_id>` | Asks a run to stop; registered only with run control |

## Errors

Every error derives from `AiError`. pydantic-ai's own are raised as pydantic-ai raises them.

| Error | Raised when |
|---|---|
| `InvalidConfigurationError` | A configuration cannot be used: an unknown platform or agent named literally, a cycle of agents, an orm adapter without its bridge or without `OrmBundle` listed, a tool for an unknown agent, a capability or tool service that is not a singleton, run-control timings that would make a live run look dead. Also a `ValueError` |
| `PlatformUnavailableError` | A platform cannot be built: unknown, its extra missing, its key unset, a keyword refused. Names the platform and the variable, never a value |
| `RunInProgressError` | A second top-level run of a conversation is started |
| `UnknownRunError` | A run is watched without being started. Also a `LookupError` |

## Known limitations

- **Message timestamps** come from the system clock: pydantic-ai stamps them itself. The clock
  bundle reaches run timeouts and run control only.
- **Agents are singletons.** Capabilities, toolsets and tool services they are built from must be
  too.
- **`isinstance(agent, Agent)`** is false for an agent with run defaults: it is a
  `RunDefaultsAgent` wrapping one.
- **`isinstance(model, OpenAIChatModel)`** is false when the platform sets `model_settings`: the
  model is a `PlatformModel` carrying them, and `model.wrapped` is the provider's own.
- **A single model request** with `pydantic_ai.direct.model_request` reads no settings from the
  model, unlike an agent run. Pass `model_settings=model.settings` to apply the platform's
  defaults.
- **Forking while deleting.** With the orm conversation store, a fork saved while its origin is
  being deleted can lose the messages they share, except on SQLite, where writes take turns.
- **The provider SDKs own HTTP.** No xtr-http-client is used. Timeouts and retries go in a
  platform's or agent's `model_settings`.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-ai`; run the commands below from there.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT
