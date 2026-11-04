"""A queued email carries no more header text than a real one writes; more is refused at decode.

The engine folds a header at a cost that grows faster than its length, so a header read from
the broker is bounded before it is built: a worker sends what it accepts in time linear in the
size of its headers, and refuses the rest as the bus's decoding error, repeating none of it.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, cast

import anyio
import pytest
from xtr_messenger import EncodedEnvelope, MessageDecodingFailedError, name_of
from xtr_mime import Email

from tests.support.growth import assert_linear_growth
from tests.support.queue import WIRE
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_mailer.messenger._wire import write
from xtr_mailer.messenger._wire._header_limits import LIST_LENGTH, VALUE_LENGTH
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from collections.abc import Callable

_COMMON: Final[dict[str, object]] = {"charset": "utf-8", "language": None}
_TEXT_HEADER: Final[dict[str, object]] = {"$type": "text", "name": "X-A", **_COMMON}


def _decoded(body: str) -> SendEmailMessage:
    decoded = WIRE.decode(EncodedEnvelope(body, {"type": name_of(SendEmailMessage)})).message
    assert isinstance(decoded, SendEmailMessage)
    return decoded


def _email_with(*added: dict[str, object]) -> str:
    written = write(Email().from_("a@example.com").to("b@example.com").text("t"), None)
    message = cast("dict[str, object]", written["message"])
    headers = cast("dict[str, list[object]]", message["headers"])
    headers["fields"] += added
    return json.dumps(written)


def _refused(body: str) -> None:
    with pytest.raises(MessageDecodingFailedError) as raised:
        _ = _decoded(body)
    for error in (raised.value, raised.value.__cause__):
        assert "ab ab" not in str(error)
        assert "victim" not in str(error)


def test_a_header_value_of_a_hundred_kilobytes_is_refused_before_it_is_rendered() -> None:
    _refused(_email_with({**_TEXT_HEADER, "value": "ab " * 43_000}))


@pytest.mark.parametrize(
    "value",
    ["v\r\nBcc: victim@example.com", "v\x00victim", "v\ud800victim"],
    ids=["line break", "null", "lone surrogate"],
)
def test_a_header_value_that_would_break_its_line_is_refused(value: str) -> None:
    _refused(_email_with({**_TEXT_HEADER, "value": value}))


def _words(size: int) -> str:
    return _email_with({**_TEXT_HEADER, "value": "ab " * (size // 3)})


def _addresses(size: int) -> str:
    entries = [{"address": f"u{i}@example.com", "name": f"User {i}"} for i in range(size)]
    return _email_with({"$type": "mailbox_list", "name": "Cc", **_COMMON, "entries": entries})


@pytest.mark.parametrize(
    ("shape", "largest"),
    [(_words, VALUE_LENGTH), (_addresses, LIST_LENGTH)],
    ids=["the longest value", "the longest address list"],
)
def test_the_largest_headers_accepted_are_read_and_sent_in_linear_time(
    shape: Callable[[int], str], largest: int
) -> None:
    def run(size: int) -> None:
        _ = anyio.run(MessageHandler(NullTransport()), _decoded(shape(size)))

    assert_linear_growth(run, largest // 4)
