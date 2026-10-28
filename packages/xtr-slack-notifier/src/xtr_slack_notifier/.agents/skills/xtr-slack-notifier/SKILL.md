---
name: xtr-slack-notifier
description: How to post chat messages to Slack with xtr-slack-notifier, the Slack provider of xtr-notifier — a slack DSN served with no wiring, SlackOptions with Block Kit blocks (sections, headers, context, buttons, inputs), threads, scheduled messages, updating a posted message through SlackSentMessage, and notifications rendered as blocks. Use when an application must notify a Slack channel, configure SLACK_DSN, lay a message out with blocks or buttons, reply in a thread, schedule or update a Slack message, or test code that posts to Slack.
---

# xtr-slack-notifier

The Slack provider of xtr-notifier. Installed beside it, a `slack://` DSN is served by
`SlackTransportFactory`, found through its entry point. For notifications, channels and the
bundle, load the `xtr-notifier` skill.

## Quick reference

- DSN — `slack://TOKEN@default?channel=CHANNEL`; `default` is `slack.com`; `ssl=false` for HTTP.
  The token must start with `xoxb-`, `xoxp-` or `xoxa-2` (`InvalidArgumentError` when built).
- `SlackTransport(access_token, channel, http_client, event_dispatcher=None)`; its string form
  never shows the token.
- `SlackOptions()` — fluent builder; `.to_options()` renders the `MessageOptions` (kind `slack`).
  `recipient(...)` wins over the DSN's channel.
- Methods — `chat.postMessage`; `chat.scheduleMessage` with `post_at(datetime)`; `chat.update`
  with `UpdateMessageSlackOptions` (kind `slack.update`).
- `send` returns a `SlackSentMessage`: `channel_id`, `message_id` (the `ts`),
  `get_update_message(subject, options=None)`.
- Blocks — `xtr_slack_notifier.block`: `SlackSectionBlock`, `SlackHeaderBlock`,
  `SlackContextBlock`, `SlackActionsBlock`, `SlackDividerBlock`, `SlackImageBlock`,
  `SlackPlainTextInputBlock`; elements `SlackButtonBlockElement`, `SlackImageBlockElement`.

## Lay a message out with blocks

```python
from xtr_notifier.message import ChatMessage
from xtr_slack_notifier import SlackOptions
from xtr_slack_notifier.block import SlackActionsBlock, SlackSectionBlock

options = (
    SlackOptions()
    .block(SlackSectionBlock().text("*Deploy 42* finished.").field("*Env*").field("prod"))
    .block(SlackActionsBlock().button("Open", "https://example.com/deploys/42", "primary"))
)
await chatter.send(ChatMessage("Deploy 42 finished.", options.to_options()))
```

## Thread, schedule, update

```python
SlackOptions().thread_ts(parent_ts)  # reply in a thread
SlackOptions().post_at(datetime(2026, 1, 1, 9, tzinfo=UTC))  # chat.scheduleMessage

sent = await transport.send(ChatMessage("Deploying..."))
await transport.send(sent.get_update_message("Deployed."))  # chat.update
```

## Notifications

A `ChatMessage.from_notification(...)` with no options is rendered by
`SlackOptions.from_notification(summary)`: emoji icon, subject and content sections, and the
traceback after a divider when the notification carries an exception.

## Testing

```python
from xtr_http_client import JsonMockResponse, MockHttpClient
from xtr_notifier.message import ChatMessage
from xtr_slack_notifier import SlackTransport


def answer(method, url, options):
    assert url == "https://slack.com/api/chat.postMessage"
    assert options["json"] == {"channel": "ops", "text": "Hi"}
    assert options["auth_bearer"] == "xoxb-T"
    return JsonMockResponse({"ok": True, "ts": "1.2", "channel": "C1"})


sent = await SlackTransport("xoxb-T", "ops", MockHttpClient(answer)).send(ChatMessage("Hi"))
assert sent.message_id == "1.2"
```

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe: it writes `SLACK_DSN` in `.env` and prints
the configuration step.

1. **Install** — `uv add xtr-slack-notifier`, beside xtr-notifier set up as the `xtr-notifier`
   skill says.
2. **Configure** — add `slack=env("SLACK_DSN")` to `chatter_transports` in
   `<app>/config/notifier.py`.
3. **Environment** — `SLACK_DSN`, `slack://TOKEN@default?channel=CHANNEL`.
4. **Check** — `debug:config notifier` lists `slack` under `chatter_transports`.
5. **Remove** — drop the entry and `SLACK_DSN`, then `uv remove xtr-slack-notifier`.

There is no bundle to activate.

## Errors

| Error | When |
|---|---|
| `IncompleteDsnError` | `User is not set.` — no token |
| `InvalidArgumentError` | A token not starting with `xoxb-`, `xoxp-` or `xoxa-2` |
| `LogicError` / `LengthError` | A block, button, field or text past Slack's limits |
| `TransportError` | `Unable to post the Slack message: "<error>" (<errors>).`; `Could not reach the remote Slack server.` |
| `UnsupportedMessageTypeError` | A message that is not a `ChatMessage` |

## Do not

- Do not write the token into code or configuration; read the DSN with `env("SLACK_DSN")`.
- Do not build update options by hand; use `SlackSentMessage.get_update_message`.
- Do not put block objects into `SlackOptions({...})`; pass `block.to_array()` or use `.block()`.
