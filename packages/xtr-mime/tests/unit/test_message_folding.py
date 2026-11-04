"""A message folds each header once per render: what it costs grows with its headers once.

Folding a long header is the costly part of rendering, so a render that folded each one more
than once — to tell whether it has a body, to write it, for the message then for its body —
would multiply that cost. Each fold is counted where the engine builds a header to fold.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

import pytest

from xtr_mime import Address, DataPart, Email, Headers, Message, MixedPart, TextPart
from xtr_mime._engine import _fold

if TYPE_CHECKING:
    from xtr_mime._engine import HeaderValue

_WIRE_NAMES = ("From", "To", "Cc", "Subject", "X-A", "X-B")


@pytest.fixture
def folds(monkeypatch: pytest.MonkeyPatch) -> Counter[str]:
    """Count, by header name, every header the engine builds to fold."""
    counted: Counter[str] = Counter()
    build = _fold._build_header

    def counting(name: str, value: HeaderValue) -> object:
        counted[name] += 1
        return build(name, value)

    monkeypatch.setattr(_fold, "_build_header", counting)
    return counted


def _headers() -> Headers:
    headers = Headers().add_mailbox_list_header("From", [Address("a@example.com", "J\u00fcrgen")])
    _ = headers.add_mailbox_list_header("To", ["b@example.com"])
    _ = headers.add_mailbox_list_header("Cc", [Address("c@example.com", "\U0001f600" * 40)])
    _ = headers.add_text_header("Subject", "\U0001f600" * 200)
    return headers.add_text_header("X-A", "Jürgen é " * 30).add_text_header("X-B", "v")


def test_a_message_folds_each_of_its_headers_once_per_render(folds: Counter[str]) -> None:
    message = Message(_headers(), TextPart("hello"))

    _ = message.to_string()

    assert {name: folds[name] for name in _WIRE_NAMES} == dict.fromkeys(_WIRE_NAMES, 1)


def test_a_part_folds_each_of_its_headers_once_per_render(folds: Counter[str]) -> None:
    attachment = DataPart(b"x", "\U0001f600" * 60 + ".txt")
    _ = attachment.get_headers().add_text_header("X-A", "\U0001f600" * 200)
    message = Message(_headers(), MixedPart(TextPart("hello"), attachment))

    _ = message.to_string()

    assert folds["X-A"] == 2
    assert folds["Content-Disposition"] == 1


def test_an_email_folds_each_of_its_headers_once_per_render(folds: Counter[str]) -> None:
    email = Email().from_("a@example.com").to("b@example.com").subject("\U0001f600" * 200)
    _ = email.text("hello")

    _ = email.to_string()

    assert (folds["Subject"], folds["To"]) == (1, 1)


def test_headers_fold_each_header_once_to_tell_its_body_and_write_it(
    folds: Counter[str],
) -> None:
    headers = _headers().add_text_header("X-Empty", "")

    fields = headers.to_array()

    assert [field.partition(":")[0] for field in fields] == list(_WIRE_NAMES)
    assert {name: folds[name] for name in (*_WIRE_NAMES, "X-Empty")} == {
        **dict.fromkeys(_WIRE_NAMES, 1),
        "X-Empty": 1,
    }
