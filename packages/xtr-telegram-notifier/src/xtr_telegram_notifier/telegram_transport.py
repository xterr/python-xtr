"""Sending chat messages through a Telegram bot."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Final, cast, final
from urllib.parse import urlencode

from typing_extensions import override
from xtr_http_client_contracts.exception import TransportError as HttpTransportError
from xtr_notifier.exception import TransportError, UnsupportedMessageTypeError
from xtr_notifier.message import ChatMessage, SentMessage
from xtr_notifier.transport import AbstractTransport

from ._markdown_v2 import escape_markdown_v2
from ._payload import (
    EXCLUSIVE_OPTIONS,
    action_for,
    build_input_media,
    ensure_exclusive_options,
    expand_options,
    form_fields,
    method_for,
    non_empty,
    text_option_for,
)
from .telegram_options import TelegramOptions

if TYPE_CHECKING:
    from io import BufferedReader

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_notifier.message import MessageInterface

__all__ = ["TelegramTransport"]


@final
class TelegramTransport(AbstractTransport):
    """Posts, edits and answers through the Telegram bot API.

    The chat a message goes to is the one its options name, else the
    channel the transport was built with. The text is sent as MarkdownV2
    unless the options pick another parse mode, escaped so that a plain
    sentence is accepted and markup written on purpose is kept.

    A file to upload is opened when the message is sent, and the fields go
    as a form body the HTTP client sends as ``multipart/form-data``; without
    one they go as JSON. The files are closed once the request is made,
    whatever came of it.

    To find a chat's id, message the bot from that chat and read
    ``https://api.telegram.org/bot<token>/getUpdates``.
    """

    HOST: ClassVar[str] = "api.telegram.org"
    #: The options that each pick what a message is; only one of them may be set.
    EXCLUSIVE_OPTIONS: Final = EXCLUSIVE_OPTIONS

    def __init__(
        self,
        token: str,
        channel: str | None,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
    ) -> None:
        """Send as the bot ``token`` to ``channel`` unless a message names its chat.

        Args:
            token: The bot's token, ``<bot id>:<secret>``; never shown.
            channel: The chat sent to when a message names none, or ``None``.
            http_client: What the bot API is reached through.
            event_dispatcher: Where the message events go; ``None`` announces nothing.
        """
        super().__init__(http_client, event_dispatcher)
        self._token = token
        self._channel = channel

    @override
    def __str__(self) -> str:
        """Name the endpoint and the channel, and ``ssl=false`` over HTTP; never the token."""
        query = {
            key: value
            for key, value in (
                ("channel", self._channel),
                ("ssl", "false" if self._get_http_scheme() == "http" else None),
            )
            if value is not None
        }
        name = f"telegram://{self._get_endpoint()}"
        return f"{name}?{urlencode(query)}" if query else name

    @override
    def __repr__(self) -> str:
        """Render as the string form, so a traceback never shows the token."""
        return f"{type(self).__name__}({str(self)!r})"

    @override
    def supports(self, message: MessageInterface) -> bool:
        """Send chat messages carrying no options or Telegram's."""
        return isinstance(message, ChatMessage) and (
            message.options is None or message.options.kind == "telegram"
        )

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        """Call the bot API method the options pick, and report the message's id.

        Raises:
            UnsupportedMessageTypeError: When ``message`` is not a chat message.
            MultipleExclusiveOptionsUsedError: When the options pick several kinds.
            LogicError: When an edit replaces a media with a file to upload.
            TransportError: When the bot API cannot be reached or refuses the message.
        """
        if not isinstance(message, ChatMessage):
            raise UnsupportedMessageTypeError(str(self), "ChatMessage", message)
        options = {} if message.options is None else dict(message.options.values)
        if options.get("chat_id") is None:
            options["chat_id"] = message.recipient_id or self._channel
        text = message.subject
        if options.get("parse_mode") in {None, TelegramOptions.PARSE_MODE_MARKDOWN_V2}:
            options["parse_mode"] = TelegramOptions.PARSE_MODE_MARKDOWN_V2
            text = escape_markdown_v2(text)
        files = _open_uploads(options)
        try:
            answer = await self._call(options, text, uploading=bool(files))
        finally:
            for file in files:
                file.close()
        return self._sent(message, answer)

    async def _call(
        self, options: dict[str, object], text: str, *, uploading: bool
    ) -> dict[str, object]:
        """Shape ``options`` into the method's fields, call it, and return what it answered."""
        text_option = text_option_for(options)
        if text_option is not None:
            options[text_option] = text
        ensure_exclusive_options(options)
        method = method_for(options)
        if method == "editMessageMedia":
            options = build_input_media(options, text)
        _ = options.pop("edit_caption", None)
        fields = non_empty(expand_options(options, "contact", "location", "venue"))
        url = f"{self._get_http_scheme()}://{self._get_endpoint()}/bot{self._token}/{method}"
        try:
            response = await (
                self._http_client.request("POST", url, body=form_fields(fields))
                if uploading
                else self._http_client.request("POST", url, json=fields)
            )
        except HttpTransportError as error:
            raise TransportError("Could not reach the remote Telegram server.") from error
        async with response:
            answer = await response.to_array(throw=False)
        if response.get_status_code() != HTTPStatus.OK:
            raise TransportError(
                f"Unable to {action_for(fields)} the Telegram message: "
                f"{answer.get('description')} (code {answer.get('error_code')}).",
                response,
            )
        return answer

    def _sent(self, message: ChatMessage, answer: Mapping[str, object]) -> SentMessage:
        """Report ``message`` sent, with the id the bot API gave it, when it gave one."""
        result = answer.get("result")
        sent = SentMessage(message, str(self))
        if isinstance(result, Mapping):
            message_id = cast("Mapping[str, object]", result).get("message_id")
            if message_id is not None:
                sent.message_id = str(message_id)
        return sent


def _open_uploads(options: dict[str, object]) -> list[BufferedReader]:
    """Replace the ``upload`` paths of ``options`` with their files, opened for reading.

    The caller closes them once the request is made.
    """
    uploads = options.pop("upload", None)
    if not isinstance(uploads, Mapping):
        return []
    files: list[BufferedReader] = []
    try:
        for option, path in cast("Mapping[str, object]", uploads).items():
            file = Path(str(path)).open("rb")  # noqa: SIM115 -- closed by the caller once sent
            files.append(file)
            options[option] = file
    except BaseException:
        for file in files:
            file.close()
        raise
    return files
