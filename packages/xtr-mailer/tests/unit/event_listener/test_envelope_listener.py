"""The listener replacing who an email is delivered for and to, with an allow-list."""

from __future__ import annotations

import pytest
from xtr_mime import Address, Email, Message, RawMessage
from xtr_mime.header import Headers

from xtr_mailer import Envelope, InvalidArgumentError
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import EnvelopeListener


def _event(message: RawMessage | None = None, *recipients: str) -> MessageEvent:
    addresses = [Address(r) for r in recipients or ("r1@example.com", "r2@example.org")]
    envelope = Envelope(Address("sender@example.com"), addresses)
    return MessageEvent(RawMessage("message") if message is None else message, envelope, "default")


def _recipients(event: MessageEvent) -> list[str]:
    return [address.get_address() for address in event.get_envelope().get_recipients()]


@pytest.mark.parametrize(
    ("expected", "recipients", "allowed_recipients"),
    [
        (["r1@example.com", "r2@example.org"], None, []),
        (["admin@admin.com"], ["admin@admin.com"], []),
        (["admin@admin.com", "r1@example.com"], ["admin@admin.com"], [r".*@example\.com"]),
        (
            ["admin@admin.com", "r1@example.com", "r2@example.org"],
            ["admin@admin.com"],
            [r".*@example\.com", r".*@example\.org"],
        ),
        (
            ["r1@example.com", "r2@example.org"],
            ["r1@example.com"],
            [r".*@example\.com", r".*@example\.org"],
        ),
    ],
)
def test_recipients(
    expected: list[str], recipients: list[str] | None, allowed_recipients: list[str]
) -> None:
    listener = EnvelopeListener(None, recipients, allowed_recipients)
    event = _event()

    listener.on_message(event)

    assert _recipients(event) == expected


def test_it_runs_last_so_other_listeners_change_the_headers_first() -> None:
    assert EnvelopeListener.PRIORITY == -255


def test_no_recipients_leaves_the_envelope_as_it_is() -> None:
    event = _event()

    EnvelopeListener(recipients=[], allowed_recipients=[r".*"]).on_message(event)

    assert _recipients(event) == ["r1@example.com", "r2@example.org"]


def test_a_recipient_may_be_written_with_a_name() -> None:
    event = _event()

    EnvelopeListener(recipients=["Admin <admin@admin.com>"]).on_message(event)

    assert event.get_envelope().get_recipients() == [Address("admin@admin.com")]


def test_the_sender_replaces_the_envelope_sender() -> None:
    event = _event()

    EnvelopeListener("Bounces <bounces@example.com>").on_message(event)

    assert event.get_envelope().get_sender() == Address("bounces@example.com", "Bounces")
    assert _recipients(event) == ["r1@example.com", "r2@example.org"]


def test_the_sender_becomes_the_sender_header_of_an_email_without_an_author() -> None:
    message = Message(Headers().add_mailbox_list_header("To", ["r1@example.com"]))
    event = _event(message)

    EnvelopeListener(Address("bounces@example.com", "Bounces")).on_message(event)

    assert message.get_headers().get_header_body("Sender") == Address(
        "bounces@example.com", "Bounces"
    )


def test_an_email_with_an_author_gets_no_sender_header() -> None:
    message = Email().from_("author@example.com").to("r1@example.com").text("Hi")
    event = _event(message)

    EnvelopeListener("bounces@example.com").on_message(event)

    assert not message.get_headers().has("Sender")
    assert event.get_envelope().get_sender() == Address("bounces@example.com")


def test_an_email_with_a_sender_header_keeps_it() -> None:
    headers = Headers().add_mailbox_header("Sender", "own@example.com")
    message = Message(headers)
    event = _event(message)

    EnvelopeListener("bounces@example.com").on_message(event)

    assert message.get_headers().get_header_body("Sender") == Address("own@example.com")


def test_an_allowed_pattern_matches_the_whole_address() -> None:
    event = _event(None, "r1@example.com", "r1@example.com.attacker.org", "r1@sub.example.com")

    EnvelopeListener(None, ["admin@admin.com"], [r"example\.com", r"r1@example\.com"]).on_message(
        event
    )

    assert _recipients(event) == ["admin@admin.com", "r1@example.com"]


def test_an_alternation_is_anchored_at_both_ends_as_a_whole() -> None:
    event = _event(None, "r1@example.com.attacker.org", "attacker-r2@example.org")

    EnvelopeListener(None, ["admin@admin.com"], [r"r1@example\.com|r2@example\.org"]).on_message(
        event
    )

    assert _recipients(event) == ["admin@admin.com"]


def test_an_allowed_recipient_is_kept_once_whichever_patterns_match_it() -> None:
    event = _event(None, "r1@example.com", "r1@example.com")

    EnvelopeListener(None, ["admin@admin.com"], [r"r1@.*", r".*@example\.com"]).on_message(event)

    assert _recipients(event) == ["admin@admin.com", "r1@example.com"]


def test_an_international_address_is_matched_as_written() -> None:
    event = _event(None, "rené@exämple.com", "r1@xn--exmple-cua.com")

    EnvelopeListener(None, ["admin@admin.com"], [r".+@exämple\.com"]).on_message(event)

    assert _recipients(event) == ["admin@admin.com", "rené@exämple.com"]


def test_the_longest_address_is_matched_at_once() -> None:
    longest = "a" * 64 + "@" + ".".join(["b" * 63, "c" * 63, "d" * 57]) + ".com"
    event = _event(None, longest)

    EnvelopeListener(None, ["admin@admin.com"], [r"[a-z]+@(?:[a-z]+\.)+com"]).on_message(event)

    assert _recipients(event) == ["admin@admin.com", longest]


def test_each_email_starts_from_the_configured_recipients() -> None:
    listener = EnvelopeListener(None, ["admin@admin.com"], [r".*@example\.com"])
    first, second = _event(None, "r1@example.com"), _event(None, "r2@other.org")

    listener.on_message(first)
    listener.on_message(second)

    assert _recipients(first) == ["admin@admin.com", "r1@example.com"]
    assert _recipients(second) == ["admin@admin.com"]


def test_a_pattern_that_is_not_a_regular_expression_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = EnvelopeListener(None, ["admin@admin.com"], [".*@(example"])

    assert str(caught.value) == (
        'The allowed recipient ".*@(example" is not a valid regular expression: '
        "missing ), unterminated subpattern at position 3."
    )
