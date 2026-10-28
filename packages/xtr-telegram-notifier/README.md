<div align="center">

# xtr-telegram-notifier

**Telegram for xtr-notifier — chat messages posted, edited and answered through a bot, with keyboards, media and file uploads, configured by DSN.**

</div>

---

## Why?

[xtr-notifier](../xtr-notifier) sends chat messages through whatever provider a DSN names. This
library is the Telegram provider: installed beside it, a `telegram://` DSN is served with no
wiring, and a message can carry everything the bot API offers — a keyboard, a photo, a location,
an edit of a message already sent, the answer to a button's callback.

## Install

```sh
uv add xtr-telegram-notifier
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
transport = Transport(discovery=discovery).from_string(
    "telegram://123456:ABC-DEF@default?channel=-1001234567890"
)

await Chatter(transport).send(ChatMessage("Deploy *finished* in 42s."))
```

## The DSN

```
telegram://BOT_ID:SECRET@default?channel=CHAT_ID
```

- `BOT_ID:SECRET` — the bot's token, as the bot API hands it out; a DSN without it, or with half
  of it, is refused with `Missing token.` or `Malformed token.`
- `default` — `api.telegram.org`; name another host (and port) to reach a local bot API server.
- `channel` — the chat a message naming none goes to. To find a chat's id, message the bot from
  that chat and read `https://api.telegram.org/bot<token>/getUpdates`.
- `ssl=false` — reach the host over plain HTTP; `sslmode=disable` is the older spelling.

The transport's string form — what errors, events and `debug:config` show — is
`telegram://api.telegram.org?channel=CHAT_ID`: never the token.

## Options

`TelegramOptions` builds what a message carries beyond its text, one call at a time;
`to_options()` renders it for the message:

```python
from xtr_notifier.message import ChatMessage
from xtr_telegram_notifier import TelegramOptions
from xtr_telegram_notifier.reply.markup import InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton

options = (
    TelegramOptions()
    .chat_id("-1001234567890")
    .disable_notification(True)
    .reply_markup(
        InlineKeyboardMarkup().inline_keyboard(
            [InlineKeyboardButton("Open").url("https://example.com/deploys/42")]
        )
    )
)
await chatter.send(ChatMessage("Deploy finished.", options.to_options()))
```

What the message is follows from the option set, and only one of these may be:

| Option | Method | The text goes in |
|---|---|---|
| none | `sendMessage` | `text` |
| `photo` / `upload_photo` | `sendPhoto` | `caption` |
| `video`, `audio`, `document`, `animation` (and `upload_*`) | `sendVideo`, … | `caption` |
| `sticker` / `upload_sticker` | `sendSticker` | not sent |
| `location`, `venue`, `contact` | `sendLocation`, `sendVenue`, `sendContact` | not sent |
| `edit(message_id)` | `editMessageText`, or `editMessageMedia` with one media by URL or file id | `text`, or the media's caption |
| `edit_caption(message_id)` | `editMessageCaption` | `caption` |
| `answer_callback_query(id, show_alert, cache_time)` | `answerCallbackQuery` | `text` |

Setting two of them raises `MultipleExclusiveOptionsUsedError`; editing a message's media with a
file to upload raises `LogicError` — the bot API takes a URL or a file id there.

The text is sent as MarkdownV2 unless `parse_mode(...)` picks `TelegramOptions.PARSE_MODE_HTML`
or `PARSE_MODE_MARKDOWN`. It is escaped first: the characters the bot API rejects unescaped
(`.`, `!`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `>`) are escaped, while markup written on purpose —
`*bold*`, `_italic_`, `` `code` ``, `~strike~`, `||spoiler||`, `[link](url)`, block quotations,
custom emojis — and characters already escaped are kept.

Keyboards: `InlineKeyboardMarkup` with `InlineKeyboardButton`s (link, login URL, callback data,
inline query, payment), `ReplyKeyboardMarkup` with `KeyboardButton`s (text, contact, location,
poll), `ReplyKeyboardRemove` and `ForceReply`.

## Uploads

`upload_photo(path)` and its siblings keep the file's **path**, so a message stays plain data and
can be queued on a message bus. The transport opens each file when it sends the message, sends
the fields as a form body — which the HTTP client sends as `multipart/form-data`, the file named
after its path — and closes the files once the request is made, whether it succeeded or not.
A message without an upload is sent as JSON.

## Errors

| Error | When |
|---|---|
| `IncompleteDsnError` | The DSN carries no token (`Missing token.`) or half of one (`Malformed token.`) |
| `UnsupportedSchemeError` | The factory was handed a DSN that is not `telegram://` |
| `UnsupportedMessageTypeError` | The transport was handed a message that is not a `ChatMessage` |
| `MultipleExclusiveOptionsUsedError` | The options pick more than one kind of message |
| `LogicError` | An edit replaces a media with a file to upload |
| `TransportError` | `Unable to post the Telegram message: <description> (code <n>).` (or `edit`, `answer callback query`), or `Could not reach the remote Telegram server.` |

Every one of them is xtr-notifier's; `TransportError` is what failover moves on from.

## Use in an application

Everything adding this package to an application takes — and, read backwards, what removing it
undoes. It ships no bundle: the notifier's bundle finds its factory by the DSN scheme.

- **Install** — `uv add xtr-telegram-notifier`, beside `xtr-notifier` set up as its
  [*Use in an application*](../xtr-notifier/README.md#use-in-an-application) says.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Environment* step below: it writes
  `TELEGRAM_DSN` in `.env`. It prints the step adding the transport to
  `<app>/config/notifier.py`, which a recipe cannot make for you.
- **Configure** — add `telegram=env("TELEGRAM_DSN")` to `chatter_transports` in
  `<app>/config/notifier.py`.
- **Environment** — `TELEGRAM_DSN`, `telegram://TOKEN@default?channel=CHAT_ID` with the bot's
  token and the chat; read when a message is first sent.
- **Remove** — drop the `chatter_transports` entry and `TELEGRAM_DSN`, then
  `uv remove xtr-telegram-notifier`.
- **Check** — `debug:config notifier` lists `telegram` under `chatter_transports`.

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
