"""Building what a Telegram message carries beyond its text."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final, Self, cast, final

from typing_extensions import override
from xtr_notifier.message import MessageOptions, MessageOptionsInterface

if TYPE_CHECKING:
    from .reply.markup.abstract_telegram_reply_markup import AbstractTelegramReplyMarkup

__all__ = ["TelegramOptions"]


@final
class TelegramOptions(MessageOptionsInterface):
    """The options of a Telegram message, one fluent call at a time.

    Each method sets a field of the bot API's request, and :meth:`to_options`
    renders them, in the order they were set, as the
    :class:`~xtr_notifier.message.MessageOptions` a message carries. What a
    message is — a photo, a location, an edit of an earlier message — is
    picked by the option set; options that each pick one cannot be combined,
    and the transport refuses a message that combines them.

    A file to upload is kept as its path, so the message stays plain data
    that crosses a message bus; the transport opens it when it sends.
    """

    #: Parse the text as HTML.
    PARSE_MODE_HTML: Final = "HTML"
    #: Parse the text as the legacy Markdown.
    PARSE_MODE_MARKDOWN: Final = "Markdown"
    #: Parse the text as MarkdownV2 — the default, escaped by the transport.
    PARSE_MODE_MARKDOWN_V2: Final = "MarkdownV2"

    __slots__ = ("_options",)

    def __init__(self, options: Mapping[str, object] | None = None) -> None:
        """Start from ``options``, the bot API's fields as they are sent.

        Args:
            options: Fields to start from; copied, so the caller's mapping
                cannot change these options.
        """
        self._options: dict[str, object] = copy.deepcopy(dict(options or {}))

    @property
    @override
    def recipient_id(self) -> str | None:
        """The chat the message goes to, or ``None`` for the transport's channel."""
        chat_id = self._options.get("chat_id")
        return None if chat_id is None else str(chat_id)

    @override
    def to_options(self) -> MessageOptions:
        """Render the options set so far — a copy, so later calls do not change it."""
        return MessageOptions("telegram", self.recipient_id, copy.deepcopy(self._options))

    def chat_id(self, chat_id: str) -> Self:
        """Send to the chat ``chat_id`` rather than the transport's channel."""
        self._options["chat_id"] = chat_id
        return self

    def message_thread_id(self, thread_id: int) -> Self:
        """Post in the forum topic ``thread_id``."""
        self._options["message_thread_id"] = thread_id
        return self

    def parse_mode(self, mode: str) -> Self:
        """Parse the text as ``mode``, one of the ``PARSE_MODE_*`` constants."""
        self._options["parse_mode"] = mode
        return self

    def disable_web_page_preview(self, disable: bool) -> Self:
        """Show no preview of the links in the text."""
        self._options["disable_web_page_preview"] = disable
        return self

    def disable_notification(self, disable: bool) -> Self:
        """Deliver the message silently."""
        self._options["disable_notification"] = disable
        return self

    def protect_content(self, protect: bool) -> Self:
        """Keep the message from being forwarded or saved."""
        self._options["protect_content"] = protect
        return self

    def has_spoiler(self, spoiler: bool) -> Self:
        """Blur the photo, video or animation until it is tapped."""
        self._options["has_spoiler"] = spoiler
        return self

    def photo(self, url: str) -> Self:
        """Send a photo, by URL or file id, with the text as its caption."""
        self._options["photo"] = url
        return self

    def upload_photo(self, path: str) -> Self:
        """Upload the photo at ``path``, with the text as its caption."""
        return self._upload("photo", path)

    def reply_to(self, message_id: int) -> Self:
        """Send the message as a reply to the message ``message_id``."""
        self._options["reply_to_message_id"] = message_id
        return self

    def reply_markup(self, markup: AbstractTelegramReplyMarkup) -> Self:
        """Show ``markup`` with the message: a keyboard, its removal, a forced reply."""
        self._options["reply_markup"] = markup.to_array()
        return self

    def edit(self, message_id: int) -> Self:
        """Edit the message ``message_id`` instead of sending one: its text, or its media."""
        self._options["message_id"] = message_id
        return self

    def edit_caption(self, message_id: int) -> Self:
        """Edit the caption of the media message ``message_id``, keeping its media.

        The subject of the message is the new caption.
        """
        self._options["message_id"] = message_id
        self._options["edit_caption"] = True
        return self

    def answer_callback_query(
        self, callback_query_id: str, show_alert: bool = False, cache_time: int = 0
    ) -> Self:
        """Answer the callback query ``callback_query_id`` a button sent, with the text.

        Args:
            callback_query_id: The query to answer.
            show_alert: Whether the text is shown as an alert rather than a toast.
            cache_time: How many seconds the answer may be cached; ``0`` or less
                leaves it to the bot API.
        """
        self._options["callback_query_id"] = callback_query_id
        self._options["show_alert"] = show_alert
        if cache_time > 0:
            self._options["cache_time"] = cache_time
        return self

    def location(self, latitude: float, longitude: float) -> Self:
        """Send a point on the map."""
        self._options["location"] = {"latitude": latitude, "longitude": longitude}
        return self

    def venue(self, latitude: float, longitude: float, title: str, address: str) -> Self:
        """Send a named place on the map."""
        self._options["venue"] = {
            "latitude": latitude,
            "longitude": longitude,
            "title": title,
            "address": address,
        }
        return self

    def document(self, url: str) -> Self:
        """Send a file, by URL or file id, with the text as its caption."""
        self._options["document"] = url
        return self

    def upload_document(self, path: str) -> Self:
        """Upload the file at ``path``, with the text as its caption."""
        return self._upload("document", path)

    def video(self, url: str) -> Self:
        """Send a video, by URL or file id, with the text as its caption."""
        self._options["video"] = url
        return self

    def upload_video(self, path: str) -> Self:
        """Upload the video at ``path``, with the text as its caption."""
        return self._upload("video", path)

    def audio(self, url: str) -> Self:
        """Send an audio file, by URL or file id, with the text as its caption."""
        self._options["audio"] = url
        return self

    def upload_audio(self, path: str) -> Self:
        """Upload the audio file at ``path``, with the text as its caption."""
        return self._upload("audio", path)

    def animation(self, url: str) -> Self:
        """Send an animation, by URL or file id, with the text as its caption."""
        self._options["animation"] = url
        return self

    def upload_animation(self, path: str) -> Self:
        """Upload the animation at ``path``, with the text as its caption."""
        return self._upload("animation", path)

    def sticker(self, url: str, emoji: str | None = None) -> Self:
        """Send a sticker, by URL or file id, tied to ``emoji``; the text is not sent."""
        self._options["sticker"] = url
        self._options["emoji"] = emoji
        return self

    def upload_sticker(self, path: str, emoji: str | None = None) -> Self:
        """Upload the sticker at ``path``, tied to ``emoji``; the text is not sent."""
        _ = self._upload("sticker", path)
        self._options["emoji"] = emoji
        return self

    def contact(
        self,
        phone_number: str,
        first_name: str,
        last_name: str | None = None,
        v_card: str | None = None,
    ) -> Self:
        """Send a phone contact, with a vCard when given; the text is not sent."""
        contact: dict[str, object] = {"phone_number": phone_number, "first_name": first_name}
        if last_name is not None:
            contact["last_name"] = last_name
        if v_card is not None:
            contact["vcard"] = v_card
        self._options["contact"] = contact
        return self

    def _upload(self, option: str, path: str) -> Self:
        """Upload the file at ``path`` as ``option``, kept by path until the send."""
        existing = self._options.get("upload")
        uploads = (
            dict(cast("Mapping[str, object]", existing)) if isinstance(existing, Mapping) else {}
        )
        uploads[option] = path
        self._options["upload"] = uploads
        return self
