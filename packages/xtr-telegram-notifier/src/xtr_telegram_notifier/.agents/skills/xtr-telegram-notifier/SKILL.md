---
name: xtr-telegram-notifier
description: How to send chat messages to Telegram with xtr-telegram-notifier, the Telegram provider of xtr-notifier — a telegram DSN served with no wiring, TelegramOptions for keyboards, photos and other media, file uploads, locations, venues, contacts, editing a sent message and answering a callback query, with MarkdownV2 escaping. Use when an application must notify a Telegram chat or channel through a bot, configure TELEGRAM_DSN, build Telegram message options or reply keyboards, upload a file to a chat, edit or answer a Telegram message, or test code that sends to Telegram.
---

# xtr-telegram-notifier

The Telegram provider of xtr-notifier. Installed beside it, a `telegram://` DSN is served by
`TelegramTransportFactory`, found through its entry point. For notifications, channels and the
bundle, load the `xtr-notifier` skill.

## Quick reference

- DSN — `telegram://BOT_ID:SECRET@default?channel=CHAT_ID`; `default` is `api.telegram.org`;
  `ssl=false` (or `sslmode=disable`) for plain HTTP. No token: `Missing token.`; half: `Malformed token.`
- `TelegramTransport(token, channel, http_client, event_dispatcher=None)`; its string form never
  shows the token.
- `TelegramOptions()` — fluent builder; `.to_options()` renders the `MessageOptions` a
  `ChatMessage` carries. `chat_id(...)` wins over the DSN's channel.
- One kind per message: `photo`, `video`, `audio`, `document`, `animation`, `sticker`,
  `location`, `venue`, `contact`, `edit`, `answer_callback_query` — two raise
  `MultipleExclusiveOptionsUsedError`.
- Text is MarkdownV2 by default, escaped (markup kept); `parse_mode(TelegramOptions.PARSE_MODE_HTML)`
  sends it as written.
- Keyboards — `xtr_telegram_notifier.reply.markup`: `InlineKeyboardMarkup`,
  `ReplyKeyboardMarkup`, `ReplyKeyboardRemove`, `ForceReply`; buttons in `.button`:
  `InlineKeyboardButton`, `KeyboardButton`.

## Send a message with a keyboard

```python
from xtr_notifier.message import ChatMessage
from xtr_telegram_notifier import TelegramOptions
from xtr_telegram_notifier.reply.markup import InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton

options = TelegramOptions().reply_markup(
    InlineKeyboardMarkup().inline_keyboard(
        [InlineKeyboardButton("Approve").callback_data("approve:42")]
    )
)
await chatter.send(ChatMessage("Deploy *42* is waiting.", options.to_options()))
```

## Send media, a place or a contact

```python
TelegramOptions().photo("https://example.com/chart.png")  # the text is the caption
TelegramOptions().upload_document("/var/reports/daily.pdf")  # opened, sent and closed at send
TelegramOptions().location(48.8566, 2.3522)  # the text is not sent
TelegramOptions().contact("+33100000000", "Ops", "Team")
```

An upload keeps its path, so the message can be queued; the transport sends the fields as a
form body the HTTP client turns into `multipart/form-data`.

## Edit or answer

```python
TelegramOptions().edit(message_id)  # editMessageText
TelegramOptions().edit(message_id).photo("https://example.com/new.png")  # editMessageMedia
TelegramOptions().edit_caption(message_id)  # editMessageCaption
TelegramOptions().answer_callback_query(query_id, show_alert=True, cache_time=5)
```

`SentMessage.message_id` is the id the bot API gave the message, as text — keep it to edit it.

## Testing

```python
from xtr_http_client import JsonMockResponse, MockHttpClient
from xtr_notifier.message import ChatMessage
from xtr_telegram_notifier import TelegramTransport


def answer(method, url, options):
    assert url == "https://api.telegram.org/bot1:T/sendMessage"
    assert options["json"] == {"chat_id": "ops", "text": "Hi", "parse_mode": "MarkdownV2"}
    return JsonMockResponse({"ok": True, "result": {"message_id": 7}})


sent = await TelegramTransport("1:T", "ops", MockHttpClient(answer)).send(ChatMessage("Hi"))
assert sent.message_id == "7"
```

An upload reaches the script as an open file under `options["body"]`.

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe: it writes `TELEGRAM_DSN` in `.env` and
prints the configuration step.

1. **Install** — `uv add xtr-telegram-notifier`, beside xtr-notifier set up as the
   `xtr-notifier` skill says.
2. **Configure** — add `telegram=env("TELEGRAM_DSN")` to `chatter_transports` in
   `<app>/config/notifier.py`.
3. **Environment** — `TELEGRAM_DSN`, `telegram://TOKEN@default?channel=CHAT_ID`.
4. **Check** — `debug:config notifier` lists `telegram` under `chatter_transports`.
5. **Remove** — drop the entry and `TELEGRAM_DSN`, then `uv remove xtr-telegram-notifier`.

There is no bundle to activate.

## Errors

| Error | When |
|---|---|
| `IncompleteDsnError` | `Missing token.` / `Malformed token.` |
| `MultipleExclusiveOptionsUsedError` | Two kinds of message picked at once |
| `LogicError` | Editing a media with a file to upload — use a URL or a file id |
| `TransportError` | `Unable to post the Telegram message: <description> (code <n>).` (or `edit`, `answer callback query`); `Could not reach the remote Telegram server.` |
| `UnsupportedMessageTypeError` | A message that is not a `ChatMessage` |

## Do not

- Do not write the bot token into code or configuration; read the DSN with `env("TELEGRAM_DSN")`.
- Do not pass open files in options; use the `upload_*` methods, which keep a path.
- Do not escape MarkdownV2 yourself; the transport does, and keeps what is already escaped.
- Do not combine `edit` with an `upload_*` media; the bot API refuses it.
