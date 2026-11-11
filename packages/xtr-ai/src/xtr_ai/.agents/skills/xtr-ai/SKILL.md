---
name: xtr-ai
description: How to configure language-model platforms and pydantic-ai agents with xtr-ai, inject them by name, give them service tools, keep their conversations and cancel their runs from another process. Use when application code needs an LLM, an agent, an OpenAI, Anthropic, Azure, Bedrock, Ollama or other provider key, a model chosen per environment, fallback models, tools on a service, an agent calling another agent, a conversation store, run status or cancellation across processes, an offline test model, the debug:ai or ai:* commands, or when adding AiBundle to an application on xtr-dependency-injection.
---

# xtr-ai

A platform is a provider with its key and endpoint, built the first time a run needs it. An agent
is a pydantic-ai agent whose model id is `<platform>:<model>`, configured once and injected by
name. Everything an application touches is pydantic-ai's own type: an `AbstractAgent`, a
`ConversationStore`, a `CancellationToken`.

## Quick reference

- Configure platforms and agents in `<app>/config/packages/ai.py`, a `@configure` function
  returning `AiConfig`. Keys go through `env("...")`.
- Inject one agent with `Annotated[AbstractAgent, Target("chat")]`, or all of them with
  `Mapping[Hashable, AbstractAgent]`.
- Choose a model per environment: `platform=env("AI_CHAT_PLATFORM", default="openai")`.
- Switch a single run: `await agent.run(prompt, model="local:llama-3.3-70b")`.
- Tools: `@as_tool(agents=("chat",))` on a method of a service. The service must be a singleton.
- Conversations: `store.load` → `agent.run(..., conversation=...)` → `store.save(result)`.
- Cancel from another process: `run_control.request_cancel(run_id)`, with the run inside
  `run_control.watch(run_id, token)`.
- Tests: `test` and `function` platforms run offline; `override_agent_model` scripts one agent.
- Without the container: `PlatformRegistry.of(Platform(...))` plus pydantic-ai's
  `ResolveModelId(registry.resolve)`.
- Depend on `PlatformInterface` and `PlatformRegistryInterface`, never on the concrete classes.
  Inject a platform with `Annotated[PlatformInterface, Target("openai")]`. A platform of your own
  implements `PlatformInterface`.

## Configure platforms and agents

```python
from pydantic_ai.usage import UsageLimits
from xtr_dependency_injection import configure, env

from xtr_ai.bundle import AgentConfig, AiConfig, ModelRef, PlatformConfig


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
        },
        agents={
            "chat": AgentConfig(
                platform="openai",
                model="gpt-5-mini",
                fallbacks=(ModelRef("local", "llama-3.3-70b"),),
                instructions="Answer briefly.",
                capabilities=({"Thinking": {"effort": "low"}},),
                usage_limits=UsageLimits(request_limit=8),
                timeout=180,
            ),
        },
    )
```

- `provider` is any pydantic-ai provider name. Install its extra: `uv add "xtr-ai[openai]"`.
- `options` passes the provider's other constructor keywords; `model_settings` on a platform are
  defaults beneath the agent's.
- `capabilities` take pydantic-ai's declarative form (`"Thinking"`, `{"MCP": {"url": ...}}`) or
  a capability class the container builds.
- `toolsets` take `ToolsetRef(service=MyToolset)` and `AgentToolRef(agent="research")`.
- `instructions_file="%kernel.project_dir%/prompts/chat.md"` reads instructions from a file.
- An agent with `usage_limits` or `timeout` is a `RunDefaultsAgent`: a call passing its own wins.

## Use an agent

```python
from typing import Annotated

from pydantic_ai.agent import AbstractAgent
from xtr_dependency_injection import Target, as_service


@as_service
class Assistant:
    def __init__(self, chat: Annotated[AbstractAgent, Target("chat")]) -> None:
        self._chat = chat

    async def answer(self, question: str) -> str:
        result = await self._chat.run(question)
        return result.output
```

## Give an agent tools

```python
from xtr_ai import as_tool


class Patients:
    def __init__(self, repository: PatientRepository) -> None:
        self._repository = repository

    @as_tool(agents=("chat",))
    async def appointments(self, patient_id: str) -> list[str]:
        """The patient's upcoming appointments."""
        return await self._repository.appointments(patient_id)
```

The class is found by the application scan and registered as a singleton. Per-run state, such as
the user, belongs in the run's `deps` (`deps_type=` on the agent, a first `RunContext`
parameter on the tool).

## Keep conversations and control runs

```python
from pydantic_ai import CancellationToken
from pydantic_ai.conversation import Conversation

conversation = await store.load(conversation_id) or Conversation(conversation_id=conversation_id)
await run_control.start(
    run_id, agent="chat", conversation_id=conversation_id, metadata={"user": user_id}
)
token = CancellationToken()
async with run_control.watch(run_id, token) as watched:
    result = await agent.run(
        prompt, run_id=run_id, conversation=conversation, cancellation_token=token
    )
    watched.record_usage(result.usage)
await store.save(result)
```

Configure them with `conversation_stores={"default": OrmConversationStoreConfig()}` and
`runs=OrmRunControlConfig()` (with `xtr-ai[orm]` installed), or the in-memory and service
configs. See [conversations and runs](references/conversations-and-runs.md).

## Testing

```python
from pydantic_ai.models.test import TestModel
from xtr_ai.testing import override_agent_model

async with override_agent_model(
    booted.container, "chat", TestModel(custom_output_text="hi")
) as agent:
    result = await agent.run("hello")
```

- Configure test platforms offline: `PlatformConfig(provider="test", options={"custom_output_text":
  "..."})` or `PlatformConfig(provider="function", options={"function": reply})`.
- A run-control backend of your own runs
  `xtr_ai.testing.run_control_contract.RunControlContract`.

## Use in an application

1. `uv add xtr-ai xtr-dependency-injection`, plus a provider extra (`"xtr-ai[openai]"`) and
   `"xtr-ai[orm]"` to keep conversations and runs in the database.
2. `uv run xtr-recipes recipes:sync`: it lists `AiBundle` and writes
   `<app>/config/packages/ai.py` with an empty `AiConfig`.
3. Or by hand: `AiBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`, imported
   from `xtr_ai.bundle`.
4. The clock, logging and console bundles come along when their packages are installed. To keep
   conversations or runs in the database, list `OrmBundle` too; it is never activated for you.
5. Add platforms and agents to `<app>/config/packages/ai.py`.
6. Set the variables your platforms read with `env(...)`; nothing else is required.
7. Nothing to ignore.
8. Check: `debug:bundles` shows `ai` listed and active; `debug:ai` lists platforms and agents.

## Errors

| Error | Raised when |
|---|---|
| `InvalidConfigurationError` | A literal unknown platform or agent, an agent cycle, an orm adapter without `xtr-ai[orm]` or without `OrmBundle` listed, a tool for an unknown agent, a non-singleton capability or tool service |
| `PlatformUnavailableError` | A platform cannot be built on first use: unknown, its extra missing, its key unset |
| `RunInProgressError` | A second top-level run of a conversation is started |
| `UnknownRunError` | `watch` on a run never started |

## Do not

- Do not read keys with `os.environ` or pass them as literals; use `env("...")`.
- Do not build provider clients yourself in application code; configure a platform.
- Do not register a tool service, capability or toolset as scoped; agents are singletons.
- Do not rely on saving a conversation in the same transaction as your own rows: stores commit
  on their own.
- Do not expect `MockClock` to freeze message timestamps: it reaches run timeouts and run
  control only.
- Do not check `isinstance(agent, Agent)`; injected agents are `AbstractAgent`.
