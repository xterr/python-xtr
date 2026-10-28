<div align="center">

# xtr-slack-notifier

**Slack for xtr-notifier — chat messages posted, scheduled and updated in a channel, with Block Kit blocks, configured by DSN.**

</div>

---

## Why?

[xtr-notifier](../xtr-notifier) sends chat messages through whatever provider a DSN names. This
library is the Slack provider: installed beside it, a `slack://` DSN is served with no wiring, a
notification is rendered as Block Kit sections, and a message can be laid out with blocks,
scheduled for later, or updated once posted.

## Install

```sh
uv add xtr-slack-notifier
```

It needs an HTTP client implementing
[xtr-http-client-contracts](../xtr-http-client-contracts) — usually
[xtr-http-client](../xtr-http-client).

## Quick start

```python
from xtr_http_client import HttpClient
from xtr_notifier import Chatter, Transport
from xtr_notifier.message import ChatMessage
from xtr_notifier.transport import TransportFactoryDiscovery

discovery = TransportFactoryDiscovery(
    TransportFactoryDiscovery.CHATTER_GROUP, http_client=HttpClient.create()
)
transport = Transport(discovery=discovery).from_string("slack://xoxb-1234@default?channel=ops")

sent = await Chatter(transport).send(ChatMessage("Deploy finished."))
```

## The DSN

```
slack://TOKEN@default?channel=CHANNEL
```

- `TOKEN` — a bot (`xoxb-`), user (`xoxp-`) or app (`xoxa-2`) token; a DSN without one is refused
  with `User is not set.`, and a token of another kind with
  `A valid Slack token needs to start with "xoxb-", "xoxp-" or "xoxa-2". ...` when the transport
  is built — on first use, since the notifier builds its transports lazily.
- `default` — `slack.com`; name another host (and port) for a test server.
- `channel` — the channel a message naming none is posted to.
- `ssl=false` — reach the host over plain HTTP.

The transport's string form — what errors, events and `debug:config` show — is
`slack://slack.com?channel=CHANNEL`: never the token. The token is sent as a bearer credential.

## Options and blocks

`SlackOptions` builds what a message carries beyond its text; `to_options()` renders it for the
message:

```python
from xtr_notifier.message import ChatMessage
from xtr_slack_notifier import SlackOptions
from xtr_slack_notifier.block import SlackActionsBlock, SlackHeaderBlock, SlackSectionBlock

options = (
    SlackOptions()
    .recipient("C0123456789")
    .block(SlackHeaderBlock("Deploy 42"))
    .block(SlackSectionBlock().text("*Finished* in 42s.").field("*Env*").field("production"))
    .block(SlackActionsBlock().button("Open", "https://example.com/deploys/42", "primary"))
)
await chatter.send(ChatMessage("Deploy 42 finished.", options.to_options()))
```

The setters are `recipient`, `as_user`, `icon_emoji`, `icon_url`, `link_names`, `mrkdwn`, `parse`,
`unfurl_links`, `unfurl_media`, `username`, `thread_ts` (reply in a thread), `post_at` (schedule
through `chat.scheduleMessage`) and `block`. A message takes up to 50 blocks.

The blocks, under `xtr_slack_notifier.block`: `SlackSectionBlock` (text, up to 10 fields, an
accessory), `SlackHeaderBlock`, `SlackContextBlock` (up to 10 texts and images),
`SlackActionsBlock` (up to 25 buttons), `SlackDividerBlock`, `SlackImageBlock` and
`SlackPlainTextInputBlock`; the elements `SlackButtonBlockElement` and `SlackImageBlockElement`.
Anything else implements `SlackBlockInterface`.

A message made from a notification and carrying no options is rendered with
`SlackOptions.from_notification(summary)`: the emoji as the icon, a section for the subject, one
for the content, and the exception's traceback after a divider.

Fields left empty — `None`, `""`, an empty list or mapping — are not sent; `False` and `0` are.

## Updating a message

The transport returns a `SlackSentMessage`, carrying the channel (`channel_id`) and the message's
`ts` (`message_id`). `get_update_message(subject, options)` makes the message replacing it, sent
through `chat.update`:

```python
sent = await chatter.send(ChatMessage("Deploying..."))
await chatter.send(sent.get_update_message("Deployed."))
```

Its options are `UpdateMessageSlackOptions(channel_id, ts, options)`, which render with the kind
`slack.update` — the transport accepts both kinds, and tells them apart by it after the message
crossed a message bus.

## Errors

| Error | When |
|---|---|
| `IncompleteDsnError` | The DSN carries no token (`User is not set.`) |
| `InvalidArgumentError` | The token does not start with `xoxb-`, `xoxp-` or `xoxa-2` |
| `UnsupportedSchemeError` | The factory was handed a DSN that is not `slack://` |
| `UnsupportedMessageTypeError` | The transport was handed a message that is not a `ChatMessage` |
| `LogicError` | More than 50 blocks, 25 buttons, or 10 fields or context elements |
| `LengthError` | A header over 150 characters, an input label or placeholder over 150, an id over 255 |
| `TransportError` | `Unable to post the Slack message: "<error>" (<errors>).` when Slack answers `ok: false`, `Unable to post the Slack message: "<body>".` on another status, or `Could not reach the remote Slack server.` |

Every one of them is xtr-notifier's; `TransportError` is what failover moves on from.

## Use in an application

Everything adding this package to an application takes — and, read backwards, what removing it
undoes. It ships no bundle: the notifier's bundle finds its factory by the DSN scheme.

- **Install** — `uv add xtr-slack-notifier`, beside `xtr-notifier` set up as its
  [*Use in an application*](../xtr-notifier/README.md#use-in-an-application) says.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Environment* step below: it writes
  `SLACK_DSN` in `.env`. It prints the step adding the transport to
  `<app>/config/notifier.py`, which a recipe cannot make for you.
- **Configure** — add `slack=env("SLACK_DSN")` to `chatter_transports` in
  `<app>/config/notifier.py`.
- **Environment** — `SLACK_DSN`, `slack://TOKEN@default?channel=CHANNEL` with the app's token and
  the channel; read when a message is first sent.
- **Remove** — drop the `chatter_transports` entry and `SLACK_DSN`, then
  `uv remove xtr-slack-notifier`.
- **Check** — `debug:config notifier` lists `slack` under `chatter_transports`.

Everything else — the bundle, the channel policy, queuing through the message bus — is
xtr-notifier's.

## Development

```sh
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run ty check
```

## License

MIT — see [LICENSE](LICENSE).
