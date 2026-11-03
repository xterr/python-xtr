"""A queued email the worker accepts costs no more to send than the queue's limits allow.

Each costly kind of header text is grown to its limit (see :mod:`tests.support.costly_emails`):
what is read is sent, in time linear in its size; one kind past its limit — the emails a
forged message would hold — is refused at decode, before anything is folded.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

import anyio
import pytest
from xtr_messenger import EncodedEnvelope, MessageDecodingFailedError, name_of
from xtr_mime import Address, DataPart, Email, Message

from tests.support.costly_emails import LIMITS, SHAPES, most_costly, queued
from tests.support.growth import assert_linear_growth
from tests.support.queue import WIRE
from xtr_mailer.messenger import MessageHandler, SendEmailMessage
from xtr_mailer.messenger._wire import write
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from collections.abc import Callable

_EMOJI = "\U0001f600"


def _decoded(body: str) -> SendEmailMessage:
    decoded = WIRE.decode(EncodedEnvelope(body, {"type": name_of(SendEmailMessage)})).message
    assert isinstance(decoded, SendEmailMessage)
    return decoded


def _sent(message: Message) -> None:
    sent = anyio.run(MessageHandler(NullTransport()), _decoded(queued(message)))
    assert sent is not None


@pytest.mark.parametrize("shape", list(SHAPES), ids=str)
def test_an_email_grown_to_a_limit_is_sent_in_time_linear_in_its_size(shape: str) -> None:
    build: Callable[[int], Message] = SHAPES[shape]

    assert_linear_growth(lambda size: _sent(build(size)), LIMITS[shape] // 4)


def test_an_email_holding_every_costly_kind_at_its_limit_is_sent() -> None:
    _sent(most_costly())


def _email() -> Email:
    return Email().from_("a@example.com").to("b@example.com").text("t")


def _with_fields(*added: dict[str, object]) -> str:
    written = write(_email(), None)
    message = cast("dict[str, dict[str, list[object]]]", written["message"])
    message["headers"]["fields"] += added
    return json.dumps(written)


def _text(value: str) -> dict[str, object]:
    return {"$type": "text", "name": "X-A", "charset": "utf-8", "language": None, "value": value}


def _cc(name: str) -> dict[str, object]:
    entries = [{"address": f"c{i}@example.com", "name": name} for i in range(64)]
    header = {"$type": "mailbox_list", "name": "Cc", "charset": "utf-8", "language": None}
    return {**header, "entries": entries}


def _attachments_holding(value: str) -> str:
    email = _email()
    for _ in range(2):
        attachment = DataPart(b"x", "a.bin")
        _ = attachment.get_headers().add_text_header("X-A", value)
        _ = email.add_part(attachment)
    return queued(email)


@pytest.mark.parametrize(
    "body",
    [
        _with_fields(*[_text(_EMOJI * 8192)] * 7, _text(_EMOJI * 8000)),
        _with_fields(_cc(_EMOJI * 998)),
        _with_fields(_cc(("J\u00fcrgen \u00e9 " * 111)[:998])),
        _attachments_holding(_EMOJI * 8192),
        queued(_email().cc(*[Address(f"c{i}@example.com", _EMOJI * 256) for i in range(5)])),
        # From and To are two of the headers the email holds.
        _with_fields(*[_text("a")] * 511),
        queued(SHAPES["tiny headers"](LIMITS["tiny headers"] + 1)),
    ],
    ids=[
        "emoji values",
        "emoji names",
        "accented names",
        "emoji parts",
        "names past the limit",
        "headers of a part",
        "headers of an email",
    ],
)
def test_an_email_past_a_limit_is_refused_at_decode_repeating_nothing(body: str) -> None:
    with pytest.raises(MessageDecodingFailedError) as raised:
        _ = _decoded(body)

    for error in (raised.value, raised.value.__cause__):
        assert _EMOJI not in str(error)
        assert "J\u00fcrgen" not in str(error)
