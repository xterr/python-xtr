"""A signed message sends the very bytes signed, however often and however it is rendered.

A body may render differently each time — an attached message makes up a new Message-ID —
or only once — a stream that cannot seek back. Each is signed, then rendered twice both ways.
A body frozen elsewhere — read back from a queue — renders the bytes it was frozen with.
"""

from __future__ import annotations

import io
import os
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.dkim_keys import DOMAIN, dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import signer, wire  # noqa: E402 -- see above.
from xtr_mime import Email, Headers, Message, MessagePart  # noqa: E402 -- see above.
from xtr_mime.crypto import SignedBody  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_TEXT = b"A body read once, and once only.\r\n"


class _OneWayReader(io.BytesIO):
    """A binary stream that says it cannot seek back, as a socket or a pipe does."""

    @override
    def seekable(self) -> bool:
        return False


def _with_attached_message() -> Email:
    inner = Email().from_("x@example.org").to("y@example.com").text("inner")
    return _email().text("outer").add_part(MessagePart(inner))


def _with_one_way_stream() -> Email:
    return _email().text(_OneWayReader(_TEXT))


def _email() -> Email:
    return Email().from_(f"fabien@{DOMAIN}").to("b@example.com").subject("Hi")


@pytest.fixture
def pipe_email() -> Iterator[Email]:
    read_end, write_end = os.pipe()
    with os.fdopen(write_end, "wb") as writer:
        _ = writer.write(_TEXT)
    with os.fdopen(read_end, "rb") as reader:
        yield _email().text(reader)


_BUILDERS = [_with_attached_message, _with_one_way_stream]


def _renderings(signed: Message) -> list[bytes]:
    return [
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
        signed.to_string().encode("utf-8", "surrogateescape"),
        wire(signed),
    ]


@pytest.mark.parametrize("build", _BUILDERS)
def test_every_rendering_of_a_signed_message_verifies(build: Callable[[], Email]) -> None:
    signed = signer().sign(build())

    assert all(dkim_key().verifies(sent) for sent in _renderings(signed))


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_signed_message_renders_the_same_bytes_every_time(build: Callable[[], Email]) -> None:
    signed = signer().sign(build())

    assert len(set(_renderings(signed))) == 1


def test_a_body_read_from_a_pipe_is_sent_as_it_was_signed(pipe_email: Email) -> None:
    signed = signer().sign(pipe_email)

    sent = wire(signed)
    assert _TEXT in sent
    assert dkim_key().verifies(sent)


def test_signing_leaves_the_message_signed_as_it_was() -> None:
    message = _with_attached_message()
    body = message.get_body()
    headers = message.get_headers().to_array()

    _ = signer().sign(message)

    assert (message.get_body(), message.get_headers().to_array()) == (body, headers)


def test_a_message_without_a_body_is_signed_with_the_empty_text_it_is_sent_with() -> None:
    headers = Headers().add_mailbox_list_header("From", [f"fabien@{DOMAIN}"])
    message = Message(headers.add_mailbox_list_header("To", ["b@example.com"]))

    signed = signer().sign(message)

    signed_body = signed.get_body()
    assert signed_body is not None
    assert signed_body.as_debug_string() == "text/plain"
    assert dkim_key().verifies(wire(signed))


def _frozen_again(body: SignedBody) -> SignedBody:
    return SignedBody.from_frozen(
        body.get_signed_part(), body.get_prepared_headers(), b"".join(body.body_to_iterable())
    )


def test_a_body_frozen_elsewhere_renders_the_bytes_it_was_frozen_with() -> None:
    signed = signer().sign(_with_attached_message())
    body = signed.get_body()
    assert isinstance(body, SignedBody)

    again = Message(signed.get_headers(), _frozen_again(body))

    assert wire(again) == wire(signed)
    assert dkim_key().verifies(wire(again))


def test_a_body_frozen_elsewhere_keeps_the_part_it_was_signed_from() -> None:
    body = signer().sign(_with_attached_message()).get_body()
    assert isinstance(body, SignedBody)

    again = _frozen_again(body)

    assert again.get_signed_part() is body.get_signed_part()
    assert again.as_debug_string() == body.as_debug_string()
