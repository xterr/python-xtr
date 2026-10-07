"""Masks secrets a caller logged, by the key that holds them or the shape they take."""

from __future__ import annotations

import copy
import dataclasses
import re
from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.formatter._text import class_name, describe, safe_str

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging_contracts import Context

    from xtr_logging.log_record import LogRecord

__all__ = ["DEFAULT_KEY_PATTERN", "DEFAULT_MASK", "RedactingProcessor"]

DEFAULT_KEY_PATTERN: Final = r"password|secret|token|authorization|api[_-]?key|cookie"
"""The keys masked unless another pattern is given: the usual carriers of secrets."""

DEFAULT_MASK: Final = "[redacted]"
"""What a masked value is replaced with."""


@final
class RedactingProcessor(ProcessorInterface):
    """Replaces secrets in a record's message, context and extra before anything writes them.

    A value is masked when its key matches ``keys`` — ``password``,
    ``api_key``, ``authorization`` and the like by default, matched anywhere in
    the key and without regard to case — so a whole secret never reaches a
    file, a terminal or a third-party sink. Matching is recursive: a key deep
    in a nested mapping, or inside a list of them, is masked too, and a
    matching key masks its whole value, however nested. A key that is not a
    string cannot match, but its value is still scanned.

    ``values`` adds patterns matched against the message and against string
    values wherever they sit; each match is replaced with the mask, so a card
    number or a bearer token pasted into an otherwise innocent message is
    caught by shape rather than by the key above it. Bytes and bytearrays are
    decoded as UTF-8 with ``errors="replace"`` for scanning — returned
    untouched when nothing matches, as the redacted text re-encoded otherwise;
    an untouched bytearray stays a bytearray. Tuples and sets come back as
    lists, like lists do. A bytes key is decoded the same way to be matched.
    Keys go through ``values`` as well, so a secret a caller used as the name
    of an entry is masked rather than written out whole; a key that is not
    text cannot be scanned and comes back as it is.

    What a formatter would otherwise turn into text behind this processor's
    back is redacted too. An exception — the logged ``exception`` and any
    other — has its message, notes, cause and context run through ``values``,
    and is masked whole when its message matches ``keys``; it comes back as a
    copy of the same class with the original traceback, or, when it cannot be
    copied, as a plain ``Exception`` carrying its class name and redacted text.
    A dataclass is redacted field by field and comes back as
    ``{class name: fields}``, the shape a formatter writes it in. Any other
    object is matched against ``values`` by the text a formatter would write
    for it, and replaced by that text redacted when anything matches.
    """

    __slots__ = ("_keys", "_mask", "_values")

    def __init__(
        self,
        keys: str | None = DEFAULT_KEY_PATTERN,
        values: Sequence[str] = (),
        *,
        mask: str = DEFAULT_MASK,
    ) -> None:
        """Mask by key and by value shape.

        Args:
            keys: A regular expression matched, case-insensitively, against
                each key; the value of a key it matches is masked. ``None``
                masks by value only.
            values: Regular expressions matched against string values
                anywhere; each match is replaced with ``mask``.
            mask: What a masked value, or a matched span, is replaced with.
        """
        self._keys: re.Pattern[str] | None = re.compile(keys, re.IGNORECASE) if keys else None
        self._values: tuple[re.Pattern[str], ...] = tuple(re.compile(pattern) for pattern in values)
        self._mask: str = mask

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with secrets in its message, context and extra masked."""
        return replace(
            record,
            message=self._redact_text(record.message),
            context=self._redact_mapping(record.context),
            extra=self._redact_mapping(record.extra),
        )

    def _redact_mapping(self, mapping: Context) -> Context:
        return {
            self._redact_text(key): self._redact_item(key, value) for key, value in mapping.items()
        }

    def _redact_key(self, key: object) -> object:
        """Return ``key`` with the value patterns applied, when it is text.

        A key carries a secret as readily as a value does, so one a caller
        named an entry after is masked here too. A key that is not text
        cannot be scanned and comes back as it is.
        """
        match key:
            case str():
                return self._redact_text(key)
            case bytes():
                return self._redact_bytes(key)
            case _:
                return key

    def _redact_item(self, key: object, value: object) -> object:
        if self._key_matches(key):
            return self._mask
        return self._redact_value(value)

    def _key_matches(self, key: object) -> bool:
        if self._keys is None:
            return False
        match key:
            case str():
                return self._keys.search(key) is not None
            case bytes():
                return self._keys.search(key.decode("utf-8", errors="replace")) is not None
            case _:
                # Any other key — legal in a nested mapping a caller logged —
                # cannot match the key pattern; its value is still scanned.
                return False

    def _redact_value(self, value: object) -> object:  # noqa: PLR0911 — one case per kind of value
        match value:
            case Mapping():
                # A logged mapping holds whatever the caller put in.
                redacted: dict[object, object] = {
                    self._redact_key(key): self._redact_item(key, item)  # pyright: ignore[reportUnknownArgumentType]  # a logged mapping holds unknown entries
                    for key, item in value.items()  # pyright: ignore[reportUnknownVariableType]  # a logged mapping holds unknown entries
                }
                return redacted
            case list() | tuple() | set() | frozenset():
                # A logged collection holds whatever the caller put in.
                return [
                    self._redact_value(item)  # pyright: ignore[reportUnknownArgumentType]  # a logged sequence holds unknown items
                    for item in value  # pyright: ignore[reportUnknownVariableType]  # a logged sequence holds unknown items
                ]
            case str():
                return self._redact_text(value)
            case bytes() | bytearray():
                return self._redact_bytes(value)
            case BaseException():
                return self._redact_error(value, {})
            case None | bool():
                return value
            case _ if dataclasses.is_dataclass(value) and not isinstance(value, type):
                fields: dict[str, object] = {
                    field.name: getattr(value, field.name) for field in dataclasses.fields(value)
                }
                return {class_name(value): self._redact_mapping(fields)}
            case _ if self._values:
                text = describe(value)
                redacted_text = self._redact_text(text)
                return value if redacted_text == text else redacted_text
            case _:
                return value

    def _redact_error(self, error: BaseException, done: dict[int, BaseException]) -> BaseException:
        """Return ``error``, or a copy of it with its text and chain redacted.

        ``done`` maps each error already seen to what it became, so a chain
        that loops back on itself is walked once. While an error is still
        being walked it maps to a stand-in carrying its class name and its
        redacted text alone: a loop reaching back to it re-attaches that,
        where re-attaching the error itself would have put the secret back
        into the chain a formatter walks.
        """
        seen = done.get(id(error))
        if seen is not None:
            return seen
        text = safe_str(error)
        masked = self._keys is not None and self._keys.search(text) is not None
        redacted_text = self._mask if masked else self._redact_text(text)
        done[id(error)] = Exception(f"{class_name(error)}: {redacted_text}")
        # add_note() only takes strings; anything else set by hand is dropped.
        notes: list[str] = [
            note
            for note in getattr(error, "__notes__", ())  # pyright: ignore[reportAny]  # notes exist only once add_note() ran
            if isinstance(note, str)
        ]
        redacted_notes = [self._redact_text(note) for note in notes]
        cause = None if error.__cause__ is None else self._redact_error(error.__cause__, done)
        context = None if error.__context__ is None else self._redact_error(error.__context__, done)
        if (
            redacted_text == text
            and redacted_notes == notes
            and cause is error.__cause__
            and context is error.__context__
        ):
            # Nothing to mask, and nothing in the chain is a stand-in, so the
            # error itself is what anything reaching it again should get.
            done[id(error)] = error
            return error
        args = (self._mask,) if masked else tuple(self._redact_value(arg) for arg in error.args)  # pyright: ignore[reportAny]  # an exception's args are whatever it was raised with
        rebuilt = self._rebuilt(error, args, redacted_text)
        done[id(error)] = rebuilt
        rebuilt.__traceback__ = error.__traceback__
        rebuilt.__cause__ = cause
        rebuilt.__context__ = context
        rebuilt.__suppress_context__ = error.__suppress_context__
        if notes:
            rebuilt.__notes__ = redacted_notes
        return rebuilt

    def _rebuilt(self, error: BaseException, args: tuple[object, ...], text: str) -> BaseException:
        """Copy ``error`` with ``args``; a stand-in when the copy would still carry the secret."""
        try:
            rebuilt = copy.copy(error)
            rebuilt.args = args
        except Exception:  # noqa: BLE001 — an exception class may refuse to be copied in any way
            rebuilt = None
        # A class whose text does not come from its args — a custom
        # ``__str__``, OSError's strerror — would print the secret anyway.
        if rebuilt is not None and safe_str(rebuilt) == text:
            return rebuilt
        return Exception(f"{class_name(error)}: {text}")

    def _redact_text(self, text: str) -> str:
        for pattern in self._values:
            text = pattern.sub(self._mask, text)
        return text

    def _redact_bytes(self, data: bytes | bytearray) -> bytes | bytearray:
        text = data.decode("utf-8", errors="replace")
        redacted = self._redact_text(text)
        # Unchanged text means no match: keep the original bytes, replacement
        # characters and all. Re-encoding only a redacted value keeps a payload
        # that was never secret byte-identical — a bytearray stays a bytearray.
        return data if redacted == text else redacted.encode("utf-8")
