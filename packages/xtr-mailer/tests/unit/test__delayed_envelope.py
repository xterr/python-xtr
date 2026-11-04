"""The envelope read from a message's headers when it is asked for, not when it is made."""

from __future__ import annotations

import re

import pytest
from xtr_mime import Address, Group, Headers, Message, PathHeader

from xtr_mailer import Envelope, InvalidArgumentError, LogicError
from xtr_mailer._delayed_envelope import DelayedEnvelope


def _headers(*, to: str = "to@example.com") -> Headers:
    return Headers().add_mailbox_list_header("To", [to])


def test_the_sender_is_the_return_path() -> None:
    returned = Address("return@example.com", "return")
    headers = _headers().add_path_header("Return-Path", returned)

    assert Envelope.create(Message(headers)).get_sender() == returned


def test_the_sender_is_the_sender_header() -> None:
    sender = Address("sender@example.com", "sender")
    headers = _headers().add_mailbox_header("Sender", sender)

    assert Envelope.create(Message(headers)).get_sender() == sender


def test_the_sender_is_the_first_author() -> None:
    author = Address("from@example.com", "from")
    headers = _headers().add_mailbox_list_header("From", [author, "some@example.com"])

    assert Envelope.create(Message(headers)).get_sender() == author


def test_the_sender_header_wins_over_the_return_path_and_the_authors() -> None:
    sender = Address("sender@example.com", "sender")
    headers = (
        _headers()
        .add_mailbox_list_header("From", [Address("from@example.com", "from"), "some@example.com"])
        .add_path_header("Return-Path", Address("return@example.com", "return"))
        .add_mailbox_header("Sender", sender)
    )

    assert Envelope.create(Message(headers)).get_sender() == sender


def test_the_return_path_wins_over_the_authors() -> None:
    returned = Address("return@example.com", "return")
    headers = (
        _headers()
        .add_mailbox_list_header("From", [Address("from@example.com", "from"), "some@example.com"])
        .add_path_header("Return-Path", returned)
    )

    assert Envelope.create(Message(headers)).get_sender() == returned


def test_the_recipients_expand_groups() -> None:
    helene, thomas = Address("helene@example.com"), Address("thomas@example.com")
    fabien = Address("fabien@example.com")
    headers = (
        Headers()
        .add_mailbox_list_header("From", ["from@example.com"])
        .add_mailbox_list_header("To", [Group("undisclosed-recipients")])
        .add_mailbox_list_header("Bcc", [Group("Friends", [helene, thomas]), fabien])
    )

    assert Envelope.create(Message(headers)).get_recipients() == [helene, thomas, fabien]


def test_the_sender_is_the_first_mailbox_of_a_group() -> None:
    author = Address("from@example.com", "from")
    headers = _headers().add_mailbox_list_header("From", [Group("Friends", [author])])

    assert Envelope.create(Message(headers)).get_sender() == author


def test_authors_without_a_mailbox_leave_no_sender() -> None:
    headers = _headers().add_mailbox_list_header("From", [Group("Automated System")])
    envelope = Envelope.create(Message(headers))

    with pytest.raises(
        LogicError, match=re.escape("Unable to determine the sender of the message.")
    ):
        _ = envelope.get_sender()


def test_a_message_without_any_author_leaves_no_sender() -> None:
    envelope = Envelope.create(Message(_headers()))

    with pytest.raises(
        LogicError, match=re.escape("Unable to determine the sender of the message.")
    ):
        _ = envelope.get_sender()


def test_a_sender_read_with_a_non_ascii_local_part_is_refused() -> None:
    message = Message(Headers(PathHeader("Return-Path", Address("fabièn@example.com"))))
    error = (
        'Invalid sender "fabièn@example.com": non-ASCII characters not supported in local-part '
        "of email."
    )

    with pytest.raises(InvalidArgumentError, match=re.escape(error)):
        _ = Envelope.create(message).get_sender()


def test_the_sender_is_read_when_asked_for() -> None:
    message = Message(_headers())
    envelope = Envelope.create(message)
    author = Address("from@example.com", "from")

    _ = message.get_headers().add_mailbox_list_header("From", [author])

    assert envelope.get_sender() == author


def test_the_recipients_are_read_from_to_cc_and_bcc_in_order() -> None:
    headers = (
        Headers()
        .add_path_header("Return-Path", "return@example.com")
        .add_mailbox_list_header("Bcc", [Address("bcc@example.com")])
        .add_mailbox_list_header("Cc", [Address("cc@example.com")])
        .add_mailbox_list_header("To", [Address("to@example.com")])
    )

    assert Envelope.create(Message(headers)).get_recipients() == [
        Address("to@example.com"),
        Address("cc@example.com"),
        Address("bcc@example.com"),
    ]


def test_the_recipients_read_keep_their_names() -> None:
    headers = (
        Headers()
        .add_path_header("Return-Path", "return@example.com")
        .add_mailbox_list_header("To", [Address("to@example.com", "to")])
        .add_mailbox_list_header("Cc", [Address("cc@example.com", "cc")])
        .add_mailbox_list_header("Bcc", [Address("bcc@example.com", "bcc")])
    )

    assert Envelope.create(Message(headers)).get_recipients() == [
        Address("to@example.com", "to"),
        Address("cc@example.com", "cc"),
        Address("bcc@example.com", "bcc"),
    ]


def test_a_message_without_recipients_has_none() -> None:
    headers = Headers().add_mailbox_list_header("From", ["from@example.com"])

    assert Envelope.create(Message(headers)).get_recipients() == []


def test_the_recipients_are_read_when_asked_for() -> None:
    message = Message(Headers())
    envelope = Envelope.create(message)

    _ = message.get_headers().add_mailbox_list_header("To", ["to@example.com"])

    assert envelope.get_recipients() == [Address("to@example.com")]


def test_a_sender_set_wins_over_the_headers() -> None:
    message = Message(_headers().add_mailbox_list_header("From", ["from@example.com"]))
    envelope = Envelope.create(message)

    envelope.set_sender(Address("bounces@example.com"))

    assert envelope.get_sender() == Address("bounces@example.com")


def test_recipients_set_win_over_the_headers() -> None:
    envelope = Envelope.create(Message(_headers()))

    envelope.set_recipients([Address("other@example.com", "Other")])

    assert envelope.get_recipients() == [Address("other@example.com")]


def test_a_sender_set_is_checked() -> None:
    envelope = Envelope.create(Message(_headers()))

    with pytest.raises(InvalidArgumentError):
        envelope.set_sender(Address("fabièn@example.com"))


def test_it_tells_whether_a_recipient_read_has_a_unicode_local_part() -> None:
    message = Message(_headers(to="dømi@dømi.fo").add_mailbox_header("Sender", "info@dømi.fo"))

    assert Envelope.create(message).any_address_has_unicode_localpart() is True


def test_create_builds_a_delayed_envelope() -> None:
    assert isinstance(Envelope.create(Message(_headers())), DelayedEnvelope)
