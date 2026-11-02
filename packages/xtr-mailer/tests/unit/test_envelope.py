"""An envelope: the sender and recipients an email is delivered with.

Upstream's cases reading the envelope from a message's headers are in
``test__delayed_envelope.py``, next to the class that reads them.
"""

from __future__ import annotations

import re
from typing import cast

import pytest
from xtr_mime import Address, Email, Headers, Message, RawMessage

from xtr_mailer import Envelope, InvalidArgumentError, LogicError


def _envelope(sender: Address, *recipients: Address) -> Envelope:
    return Envelope(sender, list(recipients or [Address("thomas@example.com")]))


def test_the_sender_is_kept() -> None:
    envelope = _envelope(Address("fabien@example.com"))

    assert envelope.get_sender() == Address("fabien@example.com")


def test_a_sender_with_a_non_ascii_local_part_is_refused() -> None:
    message = (
        'Invalid sender "fabièn@example.com": non-ASCII characters not supported in local-part '
        "of email."
    )

    with pytest.raises(InvalidArgumentError, match=re.escape(message)):
        _ = _envelope(Address("fabièn@example.com"))


def test_a_sender_with_a_non_ascii_domain_is_kept() -> None:
    envelope = _envelope(Address("info@dømi.fo"))

    assert envelope.get_sender() == Address("info@dømi.fo")


def test_the_sender_keeps_its_name() -> None:
    sender = Address("fabien@example.com", "Fabien")

    assert _envelope(sender).get_sender() == sender


def test_the_recipients_lose_their_names() -> None:
    envelope = _envelope(
        Address("fabien@example.com"),
        Address("thomas@example.com"),
        Address("lucas@example.com", "Lucas"),
    )

    assert envelope.get_recipients() == [
        Address("thomas@example.com"),
        Address("lucas@example.com"),
    ]


def test_an_envelope_without_recipients_is_refused() -> None:
    with pytest.raises(
        InvalidArgumentError, match=re.escape("An envelope must have at least one recipient.")
    ):
        _ = Envelope(Address("fabien@example.com"), [])


def test_a_recipient_that_is_not_an_address_is_refused() -> None:
    recipients = [cast("Address", cast("object", "lucas@example.com"))]
    message = 'A recipient must be an instance of "xtr_mime.Address" (got "str").'

    with pytest.raises(InvalidArgumentError, match=re.escape(message)):
        _ = Envelope(Address("fabien@example.com"), recipients)


def test_a_sender_that_is_not_an_address_is_refused() -> None:
    sender = cast("Address", cast("object", "fabien@example.com"))
    message = 'The sender must be an instance of "xtr_mime.Address" (got "str").'

    with pytest.raises(InvalidArgumentError, match=re.escape(message)):
        _ = Envelope(sender, [Address("thomas@example.com")])


def test_setting_the_recipients_replaces_them() -> None:
    envelope = _envelope(Address("fabien@example.com"))

    envelope.set_recipients([Address("helene@example.com", "Hélène")])

    assert envelope.get_recipients() == [Address("helene@example.com")]


def test_setting_the_sender_replaces_it() -> None:
    envelope = _envelope(Address("fabien@example.com"))

    envelope.set_sender(Address("helene@example.com"))

    assert envelope.get_sender() == Address("helene@example.com")


def test_changing_the_returned_recipients_leaves_the_envelope_alone() -> None:
    envelope = _envelope(Address("fabien@example.com"))

    envelope.get_recipients().append(Address("helene@example.com"))

    assert envelope.get_recipients() == [Address("thomas@example.com")]


@pytest.mark.parametrize(
    ("recipients", "expected"),
    [
        pytest.param(["info@dømi.fo"], False, id="ascii-local-parts"),
        pytest.param(["dømi@dømi.fo"], True, id="unicode-local-part"),
        pytest.param(["info@dømi.fo", "dømi@dømi.fo"], True, id="one-unicode-local-part"),
    ],
)
def test_it_tells_whether_an_address_has_a_unicode_local_part(
    recipients: list[str], *, expected: bool
) -> None:
    # dømi means example and is reserved by the .fo registry.
    envelope = Envelope(Address("info@dømi.fo"), [Address(r) for r in recipients])

    assert envelope.any_address_has_unicode_localpart() is expected


def test_create_refuses_a_raw_message() -> None:
    with pytest.raises(
        LogicError,
        match=re.escape("Cannot send a RawMessage instance without an explicit Envelope."),
    ):
        _ = Envelope.create(RawMessage("Some raw email message"))


def test_create_refuses_a_raw_message_of_a_subclass() -> None:
    class _Raw(RawMessage):
        pass

    with pytest.raises(LogicError):
        _ = Envelope.create(_Raw("Some raw email message"))


def test_create_reads_an_email() -> None:
    email = Email().from_("fabien@example.com").to("helene@example.com")

    envelope = Envelope.create(email)

    assert envelope.get_sender() == Address("fabien@example.com")
    assert envelope.get_recipients() == [Address("helene@example.com")]


def test_create_returns_an_envelope() -> None:
    message = Message(Headers().add_mailbox_list_header("To", ["to@example.com"]))

    assert isinstance(Envelope.create(message), Envelope)


def test_a_long_refused_sender_is_shown_cut_short() -> None:
    local_part = "é" * 70

    with pytest.raises(InvalidArgumentError) as raised:
        _ = _envelope(Address(f"{local_part}@example.com"))

    assert str(raised.value) == (
        f'Invalid sender "{"é" * 64}…": non-ASCII characters not supported in local-part of email.'
    )
