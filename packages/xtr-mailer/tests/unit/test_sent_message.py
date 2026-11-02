"""A message as it was sent: the original, what was rendered from it, and the envelope."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_mime import Address, Email, RawMessage, RfcComplianceError
from xtr_mime import LogicError as MimeLogicError

from xtr_mailer import Envelope, SentMessage

if TYPE_CHECKING:
    from collections.abc import Generator


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("text")


class _CountingEmail(Email):
    """An email that counts how often it, or a copy of it, is rendered."""

    def __init__(self) -> None:
        super().__init__()
        # A copy shares the list, so the copy a sent message renders is counted too.
        self.renderings: list[None] = []

    @override
    def to_iterable(self) -> Generator[bytes, None, None]:
        self.renderings.append(None)
        yield from super().to_iterable()


def test_a_raw_message_is_sent_as_it_is() -> None:
    raw = RawMessage("Email")
    envelope = _envelope()

    sent = SentMessage(raw, envelope)

    assert sent.get_original_message() is raw
    assert sent.get_message() is raw
    assert sent.get_envelope() is envelope
    assert sent.to_string() == raw.to_string()
    assert list(sent.to_iterable()) == list(raw.to_iterable())


def test_an_email_is_sent_as_a_rendered_copy() -> None:
    email = _email()

    sent = SentMessage(email, _envelope())

    assert sent.get_original_message() is email
    assert sent.get_message() is not email
    assert type(sent.get_message()) is RawMessage


def test_an_email_gets_a_message_id() -> None:
    sent = SentMessage(_email(), _envelope())

    assert re.fullmatch(r"[0-9a-f]{32}@example\.com", sent.get_message_id())
    assert f"Message-ID: <{sent.get_message_id()}>\r\n" in sent.to_string()


def test_the_original_email_is_left_without_a_message_id() -> None:
    email = _email()

    _ = SentMessage(email, _envelope())

    assert not email.get_headers().has("Message-ID")


def test_the_message_id_of_an_email_is_kept() -> None:
    email = _email()
    _ = email.get_headers().add_id_header("Message-ID", "kept@example.com")

    sent = SentMessage(email, _envelope())

    assert sent.get_message_id() == "kept@example.com"
    assert "Message-ID: <kept@example.com>\r\n" in sent.to_string()


def test_an_email_is_rendered_once() -> None:
    email = _CountingEmail().from_("fabien@example.com").to("helene@example.com").text("text")

    sent = SentMessage(email, _envelope())
    first = sent.to_string()

    assert sent.to_string() == first
    assert b"".join(sent.to_iterable()).decode() == first
    assert len(email.renderings) == 1
    assert "text" in first


def test_an_invalid_email_is_refused() -> None:
    email = Email().from_("fabien@example.com").text("text")

    with pytest.raises(MimeLogicError, match=re.escape('An email must have a "To", "Cc", or')):
        _ = SentMessage(email, _envelope())


def test_a_raw_message_has_no_message_id_until_one_is_set() -> None:
    sent = SentMessage(RawMessage("Email"), _envelope())

    assert sent.get_message_id() == ""


def test_the_transport_sets_the_message_id() -> None:
    sent = SentMessage(_email(), _envelope())

    sent.set_message_id("queued-as-42")

    assert sent.get_message_id() == "queued-as-42"


def test_the_debug_log_is_appended_to() -> None:
    sent = SentMessage(RawMessage("Email"), _envelope())

    sent.append_debug("> EHLO\r\n")
    sent.append_debug("< 250 OK\r\n")

    assert sent.get_debug() == "> EHLO\r\n< 250 OK\r\n"


def test_the_debug_log_starts_empty() -> None:
    assert SentMessage(RawMessage("Email"), _envelope()).get_debug() == ""


def test_a_header_the_engine_refuses_stops_the_email_before_it_is_sent() -> None:
    email = _email()
    _ = email.get_headers().add_text_header("X-Tag", "a\r\nBcc: victim@example.com")

    with pytest.raises(RfcComplianceError) as raised:
        _ = SentMessage(email, _envelope())

    assert "\r" not in str(raised.value)
