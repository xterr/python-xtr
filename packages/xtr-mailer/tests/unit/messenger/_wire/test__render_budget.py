"""What a queued email may hold across its headers and parts, each limit met then passed by one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_mime import (
    Address,
    DataPart,
    Email,
    Headers,
    Message,
    MessagePart,
    MixedPart,
    RawMessage,
    SignedBody,
    TextPart,
)

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._render_budget import (
    ADDRESS_COUNT,
    FOREIGN_NAME_WORDS,
    FOREIGN_TEXT_LENGTH,
    FOREIGN_VALUE_LENGTH,
    HEADER_COUNT,
    HEADER_TEXT_LENGTH,
    NAME_TEXT_LENGTH,
    PART_COUNT,
    WORD_OCTETS,
    check_render_cost,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_EMOJI = "\U0001f600"
# A name of 128 one-letter words beyond ASCII, as long as a name may be.
_WORDS = " ".join(["\u00e9"] * 128)


def _message(*values: str, body: object = None) -> Message:
    headers = Headers()
    for value in values:
        _ = headers.add_text_header("X-A", value)
    return Message(headers, body if isinstance(body, TextPart | MixedPart) else None)


def _header_text(size: int) -> Message:
    # "X-A" and 8000 characters a header, the last one what is left.
    values = ["a" * 7997] * (size // 8000) + ["a" * (size % 8000 - 3)]
    return _message(*values)


def _addresses(size: int) -> Message:
    headers = Headers()
    for start in range(0, size, 1000):
        listed = [f"u{i}@example.com" for i in range(start, min(size, start + 1000))]
        _ = headers.add_mailbox_list_header(f"X-L{start}", listed)
    return Message(headers)


def _listed(names: list[str], name: str = "Cc") -> Message:
    addresses = [Address(f"u{i}@example.com", held) for i, held in enumerate(names)]
    return Message(Headers().add_mailbox_list_header(name, addresses))


def _named(name: str, size: int) -> Message:
    return _listed([name * 256] * (size // 256) + [name * (size % 256)])


def _foreign_value(size: int) -> Message:
    return _message("\u00e9" * (size // 2))


def _foreign_text(size: int) -> Message:
    return _message(*["\u00e9" * 8192] * (size // 16384), "\u00e9" * (size % 16384 // 2))


def _foreign_names(size: int) -> Message:
    return _listed([_WORDS] * (size // 128) + [" ".join(["\u00e9"] * (size % 128))])


def _parts(size: int) -> Message:
    return Message(Headers(), MixedPart(*[TextPart("t") for _ in range(size - 1)]))


def _header_count(size: int) -> Message:
    # The text part writes two headers: Content-Type and Content-Transfer-Encoding.
    return _message(*["a"] * (size - 2), body=TextPart("t"))


_LIMITS: list[tuple[Callable[[int], Message], int, str]] = [
    (_header_text, HEADER_TEXT_LENGTH, "characters of header text"),
    (_addresses, ADDRESS_COUNT, "addresses"),
    (lambda size: _named("a", size), NAME_TEXT_LENGTH, "characters of names beside addresses"),
    (_foreign_value, FOREIGN_VALUE_LENGTH, "a value of more than 16384 octets beyond ASCII"),
    (_foreign_text, FOREIGN_TEXT_LENGTH, "octets of header text beyond ASCII"),
    (_foreign_names, FOREIGN_NAME_WORDS, "words of names beyond ASCII"),
    (_parts, PART_COUNT, "parts"),
    (_header_count, HEADER_COUNT, "headers"),
]
_IDS = [
    "header text",
    "addresses",
    "names",
    "value",
    "text",
    "names beyond ASCII",
    "parts",
    "headers",
]


@pytest.mark.parametrize(("shape", "limit", "reason"), _LIMITS, ids=_IDS)
def test_an_email_at_a_limit_is_read(
    shape: Callable[[int], Message], limit: int, reason: str
) -> None:
    del reason

    check_render_cost(shape(limit))


@pytest.mark.parametrize(("shape", "limit", "reason"), _LIMITS, ids=_IDS)
def test_an_email_past_a_limit_is_refused_saying_which(
    shape: Callable[[int], Message], limit: int, reason: str
) -> None:
    step = 2 if shape in {_foreign_value, _foreign_text} else 1

    with pytest.raises(InvalidArgumentError) as raised:
        check_render_cost(shape(limit + step))

    assert str(raised.value).startswith("The queued email cannot be read: message holds ")
    assert reason in str(raised.value)
    assert "\u00e9" not in str(raised.value)


def test_a_file_name_counts_each_time_it_is_written() -> None:
    email = Email().attach(b"x", _EMOJI * (FOREIGN_TEXT_LENGTH // 12 + 1))

    with pytest.raises(InvalidArgumentError, match="octets of header text beyond ASCII"):
        check_render_cost(email)


def _refused_as_too_many_words(names: list[str]) -> None:
    with pytest.raises(InvalidArgumentError, match="words of names beyond ASCII"):
        check_render_cost(_listed(names))


def test_a_word_of_a_name_beyond_ascii_of_up_to_24_octets_counts_once() -> None:
    check_render_cost(_listed(["\u00e9" * (WORD_OCTETS // 2)] * FOREIGN_NAME_WORDS))


def test_a_word_of_more_octets_counts_once_for_every_24_it_holds() -> None:
    word = "\u00e9" * (WORD_OCTETS // 2 + 1)

    _refused_as_too_many_words([word] * (FOREIGN_NAME_WORDS // 2 + 1))


def test_a_word_longer_than_24_characters_counts_once_a_character() -> None:
    word = "a" * 24 + "\u00e9"

    _refused_as_too_many_words([word] * (FOREIGN_NAME_WORDS // len(word) + 1))


def test_only_spaces_and_tabs_end_a_word_of_a_name() -> None:
    # Other spaces are not where a header folds: the engine reads one long word.
    word = "\u00e9\u00a0" * 6 + "\u00e9\u3000" * 6 + "\u00e9"

    _refused_as_too_many_words([word] * (FOREIGN_NAME_WORDS // len(word) + 1))


def test_the_bcc_of_a_message_counts_by_its_addresses_alone_as_sending_leaves_it_out() -> None:
    check_render_cost(_listed([_WORDS] * 1000, "Bcc"))


def test_the_addresses_of_the_bcc_of_a_message_are_counted() -> None:
    with pytest.raises(InvalidArgumentError, match="more than 2000 addresses"):
        check_render_cost(_listed([""] * (ADDRESS_COUNT + 1), "Bcc"))


def test_a_bcc_a_part_carries_is_counted_as_it_is_written() -> None:
    part = TextPart("t")
    _ = part.get_headers().add_mailbox_list_header("Bcc", [Address("u@example.com", _WORDS)] * 9)

    with pytest.raises(InvalidArgumentError, match="words of names beyond ASCII"):
        check_render_cost(_message(body=part))


def test_the_attachments_of_an_email_are_counted_as_parts() -> None:
    email = Email()
    for _ in range(PART_COUNT + 1):
        _ = email.add_part(DataPart(b"x", "a.bin"))

    with pytest.raises(InvalidArgumentError, match="more than 256 parts"):
        check_render_cost(email)


def test_the_headers_of_an_attached_message_are_counted() -> None:
    inner = _message("\u00e9" * 8192, "\u00e9" * 8192)
    outer = _message("\u00e9", body=MixedPart(TextPart("t"), MessagePart(inner)))

    with pytest.raises(InvalidArgumentError, match="octets of header text beyond ASCII"):
        check_render_cost(outer)


def test_a_raw_message_folds_no_header_and_costs_nothing() -> None:
    check_render_cost(RawMessage(b"Subject: " + b"a" * HEADER_TEXT_LENGTH + b"\r\n\r\nhi"))


def test_a_part_frozen_at_signing_is_counted_by_the_headers_it_was_frozen_with() -> None:
    signed = TextPart("t")
    _ = signed.get_headers().add_text_header("X-A", "\u00e9" * 8192)
    frozen = SignedBody.from_frozen(signed, Headers().add_text_header("X-B", "v"), b"t\r\n")

    check_render_cost(_message("\u00e9" * 8192, "\u00e9" * 8192, body=MixedPart(frozen)))
