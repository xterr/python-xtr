"""The message the mailer queues an email on the bus with."""

from __future__ import annotations

import io
import sys

import pytest
from pydantic import TypeAdapter
from pydantic_core import PydanticSerializationError
from typing_extensions import override
from xtr_mime import Address, Email, RawMessage
from xtr_serializer import JsonEncoder, NotNormalizableValueError, PydanticNormalizer, Serializer

from xtr_mailer import Envelope
from xtr_mailer.messenger import SendEmailMessage

_SERIALIZER = Serializer([PydanticNormalizer()], [JsonEncoder()])


class _OneWayReader(io.BytesIO):
    """A binary stream that cannot seek back, as a pipe cannot."""

    @override
    def seekable(self) -> bool:
        return False


def _email(subject: str = "Hi") -> Email:
    return Email().from_("a@example.com").to("secret@example.com").subject(subject).text("Hi")


def test_it_carries_the_email_and_its_envelope() -> None:
    raw = RawMessage("raw")
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])

    message = SendEmailMessage(raw, envelope)

    assert message.message is raw
    assert message.envelope is envelope


def test_without_an_envelope_the_one_the_headers_give_is_used_later() -> None:
    assert SendEmailMessage(RawMessage("raw")).envelope is None


def test_it_cannot_be_changed() -> None:
    message = SendEmailMessage(RawMessage("raw"))

    with pytest.raises(AttributeError):
        # Assigning to a read-only property is the point.
        message.envelope = None  # pyright: ignore[reportAttributeAccessIssue]  # ty: ignore[invalid-assignment]


def test_two_queued_emails_are_equal_when_they_travel_as_the_same_data() -> None:
    assert SendEmailMessage(RawMessage("raw")) == SendEmailMessage(RawMessage(b"raw"))


def test_two_queued_emails_differ_when_their_emails_do() -> None:
    assert SendEmailMessage(_email("One")) != SendEmailMessage(_email("Two"))


def test_a_queued_email_is_equal_to_no_other_kind_of_value() -> None:
    assert SendEmailMessage(RawMessage("raw")) != "raw"


def test_what_it_travels_as_is_taken_once_so_a_stream_is_read_once() -> None:
    message = SendEmailMessage(RawMessage(_OneWayReader(b"once")))

    first = message.written()

    assert message.written() is first
    assert message == SendEmailMessage(RawMessage(b"once"))


def test_its_repr_names_the_classes_not_the_addresses() -> None:
    envelope = Envelope(Address("from@example.com"), [Address("secret@example.com")])

    shown = repr(SendEmailMessage(_email(), envelope))

    assert shown == "SendEmailMessage(Email, envelope=Envelope)"


def test_it_is_written_and_read_back_by_a_serializer() -> None:
    message = SendEmailMessage(_email(), None)

    back = _SERIALIZER.deserialize(_SERIALIZER.serialize(message, "json"), SendEmailMessage, "json")

    assert back == message
    assert type(back.message) is Email


def test_an_email_that_cannot_be_queued_is_refused_in_its_own_words() -> None:
    class _Custom(Email):
        pass

    with pytest.raises(NotNormalizableValueError) as raised:
        _ = _SERIALIZER.serialize(SendEmailMessage(_Custom()), "json")

    assert "_Custom" in str(raised.value)


def test_without_the_serializer_package_the_mailers_own_error_is_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Custom(Email):
        pass

    monkeypatch.setitem(sys.modules, "xtr_serializer", None)

    with pytest.raises(PydanticSerializationError, match="InvalidArgumentError"):
        _ = TypeAdapter(SendEmailMessage).dump_json(SendEmailMessage(_Custom()))


def test_a_queued_email_read_from_python_is_kept_as_it_is() -> None:
    message = SendEmailMessage(RawMessage("raw"))

    assert TypeAdapter(SendEmailMessage).validate_python(message) is message
