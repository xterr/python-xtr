"""Turning a message's options into the bot API method and the fields it is called with.

Every function reads or returns the fields as a plain mapping. What a message
is follows from which field is set: ``photo`` makes it ``sendPhoto``,
``message_id`` makes it an edit, and so on down :data:`EXCLUSIVE_OPTIONS`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from io import IOBase
from typing import Final, cast

from xtr_notifier.exception import LogicError, MultipleExclusiveOptionsUsedError

__all__ = [
    "EXCLUSIVE_OPTIONS",
    "action_for",
    "build_input_media",
    "ensure_exclusive_options",
    "expand_options",
    "form_fields",
    "method_for",
    "non_empty",
    "text_option_for",
]

#: The options that each pick what a message is; only one of them may be set.
EXCLUSIVE_OPTIONS: Final = (
    "message_id",
    "callback_query_id",
    "photo",
    "location",
    "audio",
    "document",
    "video",
    "animation",
    "venue",
    "contact",
    "sticker",
)

_MEDIA_TYPES: Final = ("photo", "video", "document", "audio", "animation")
_SPOILER_MEDIA_TYPES: Final = ("photo", "video", "animation")
# Checked in this order: the first one set names the method.
_SEND_METHODS: Final = (
    ("photo", "sendPhoto"),
    ("location", "sendLocation"),
    ("audio", "sendAudio"),
    ("document", "sendDocument"),
    ("video", "sendVideo"),
    ("animation", "sendAnimation"),
    ("venue", "sendVenue"),
    ("contact", "sendContact"),
    ("sticker", "sendSticker"),
)
# Checked in this order: the option a message's text goes in, None when it is not sent.
_TEXT_OPTIONS: Final = (
    ("edit_caption", "caption"),
    ("photo", "caption"),
    ("audio", "caption"),
    ("document", "caption"),
    ("video", "caption"),
    ("animation", "caption"),
    ("sticker", None),
    ("location", None),
    ("venue", None),
    ("contact", None),
)


def _is_set(options: Mapping[str, object], key: str) -> bool:
    """Tell whether ``key`` is set to something other than ``None``."""
    return options.get(key) is not None


def method_for(options: Mapping[str, object]) -> str:
    """Return the bot API method a message with ``options`` is sent with."""
    if _is_set(options, "message_id"):
        return _edit_method_for(options)
    if _is_set(options, "callback_query_id"):
        return "answerCallbackQuery"
    return next(
        (method for option, method in _SEND_METHODS if _is_set(options, option)), "sendMessage"
    )


def _edit_method_for(options: Mapping[str, object]) -> str:
    """Return the edit method: the media, the caption, or the text."""
    if any(_is_set(options, media_type) for media_type in _MEDIA_TYPES):
        return "editMessageMedia"
    return "editMessageCaption" if _is_set(options, "edit_caption") else "editMessageText"


def action_for(options: Mapping[str, object]) -> str:
    """Return what sending ``options`` does, as an error message names it."""
    if _is_set(options, "message_id"):
        return "edit"
    if _is_set(options, "callback_query_id"):
        return "answer callback query"
    return "post"


def text_option_for(options: Mapping[str, object]) -> str | None:
    """Return the field a message's text goes in, or ``None`` when its kind sends no text."""
    return next(
        (text_option for option, text_option in _TEXT_OPTIONS if _is_set(options, option)),
        "text",
    )


def ensure_exclusive_options(options: Mapping[str, object]) -> None:
    """Refuse options that pick more than one kind of message.

    Editing a message replaces its media, so ``message_id`` goes with one media type.

    Raises:
        MultipleExclusiveOptionsUsedError: When more than one is set.
    """
    used = [key for key in options if key in EXCLUSIVE_OPTIONS]
    if "message_id" in options and sum(key in _MEDIA_TYPES for key in options) == 1:
        used.remove("message_id")
    if len(used) > 1:
        raise MultipleExclusiveOptionsUsedError(used, EXCLUSIVE_OPTIONS)


def build_input_media(options: Mapping[str, object], text: str) -> dict[str, object]:
    """Move the media of an edit, with its caption, parse mode and spoiler, into ``media``.

    Raises:
        LogicError: When the media is a file being uploaded: the bot API takes an
            edit's new media as a URL or a file id only.
    """
    built = dict(options)
    media_type = next((kind for kind in _MEDIA_TYPES if _is_set(built, kind)), None)
    if media_type is None:
        return built
    if isinstance(built[media_type], IOBase):
        raise LogicError(
            "Editing a message with a locally uploaded media is not supported yet, "
            "use a URL or a Telegram file ID instead."
        )
    media: dict[str, object] = {"type": media_type, "media": built[media_type], "caption": text}
    if _is_set(built, "parse_mode"):
        media["parse_mode"] = built["parse_mode"]
    if _is_set(built, "has_spoiler") and media_type in _SPOILER_MEDIA_TYPES:
        media["has_spoiler"] = built["has_spoiler"]
    for key in (media_type, "caption", "parse_mode", "has_spoiler"):
        _ = built.pop(key, None)
    built["media"] = media
    return built


def expand_options(options: Mapping[str, object], *keys: str) -> dict[str, object]:
    """Replace each of ``keys`` holding a mapping by that mapping's fields, at the top level."""
    expanded = dict(options)
    for key in keys:
        if not _is_set(expanded, key):
            continue
        value = expanded[key]
        if isinstance(value, Mapping):
            expanded.update(cast("Mapping[str, object]", value))
        del expanded[key]
    return expanded


def non_empty(options: Mapping[str, object]) -> dict[str, object]:
    """Drop the fields left empty — ``None``, ``False``, ``0``, ``""``, an empty collection."""
    return {key: value for key, value in options.items() if value}


def form_fields(fields: Mapping[str, object]) -> dict[str, object]:
    """Render ``fields`` for a multipart body: each nested value as JSON text.

    A form part holds one scalar, so the bot API reads an object or a list sent
    beside an upload — a reply markup, a media group — as JSON. Scalars and the
    files are left as they are.
    """
    return {
        key: json.dumps(value)
        if isinstance(value, Mapping)
        or (isinstance(value, Sequence) and not isinstance(value, (str, bytes)))
        else value
        for key, value in fields.items()
    }
