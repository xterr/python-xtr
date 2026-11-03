"""A header collection's rules: unique names, the class each name takes, bodies and parameters,
names refused, and how the collection renders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar

import pytest

from tests.support.header_lookup import header_of
from tests.support.wire import assert_folded, decode
from xtr_mime import Address
from xtr_mime.exception import LogicError, RfcComplianceError
from xtr_mime.header import (
    DateHeader,
    Headers,
    IdentificationHeader,
    PathHeader,
    UnstructuredHeader,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def test_is_unique_header_is_not_case_sensitive() -> None:
    assert Headers.is_unique_header("From")
    assert not Headers.is_unique_header("X-Foo")


def test_a_unique_header_cannot_be_added_twice() -> None:
    headers = Headers().add_text_header("Subject", "a")

    with pytest.raises(LogicError) as caught:
        _ = headers.add_text_header("subject", "b")

    assert str(caught.value) == (
        'Impossible to set header "subject" as it\'s already defined and must be unique.'
    )


def test_a_header_of_the_wrong_class_for_its_name_is_refused() -> None:
    with pytest.raises(LogicError) as caught:
        _ = Headers(UnstructuredHeader("From", "someone"))

    assert str(caught.value) == (
        'The "From" header must be an instance of "xtr_mime.header.MailboxListHeader" '
        '(got "xtr_mime.header.UnstructuredHeader").'
    )


def test_in_reply_to_names_both_classes_it_takes() -> None:
    header = DateHeader("In-Reply-To", datetime.now(UTC))

    with pytest.raises(LogicError) as caught:
        Headers.check_header_class(header)

    assert str(caught.value) == (
        'The "In-Reply-To" header must be an instance of "xtr_mime.header.UnstructuredHeader" '
        'or "xtr_mime.header.IdentificationHeader" (got "xtr_mime.header.DateHeader").'
    )


def test_a_subclass_of_the_expected_class_is_accepted() -> None:
    class CustomHeader(UnstructuredHeader):
        __slots__: ClassVar[tuple[str, ...]] = ()

    Headers.check_header_class(CustomHeader("References", "foobar"))


def test_to_string_joins_headers_together() -> None:
    headers = Headers().add_text_header("Foo", "bar").add_text_header("Zip", "buttons")

    assert headers.to_string() == "Foo: bar\r\nZip: buttons\r\n"


def test_headers_without_bodies_are_not_displayed() -> None:
    headers = Headers().add_text_header("Foo", "bar").add_text_header("Zip", "")

    assert headers.to_string() == "Foo: bar\r\n"


class _WrittenElsewhere:
    """A header of an application's own, built on no class of this package."""

    def __init__(self, name: str, body: str) -> None:
        self._name: str = name
        self._body: str = body

    def set_body(self, body: object) -> None:
        self._body = str(body)

    def get_body(self) -> object:
        return self._body

    def set_charset(self, charset: str) -> None:
        del charset

    def get_charset(self) -> str:
        return "utf-8"

    def set_language(self, language: str) -> None:
        del language

    def get_language(self) -> str | None:
        return None

    def get_name(self) -> str:
        return self._name

    def set_max_line_length(self, line_length: int) -> None:
        del line_length

    def get_max_line_length(self) -> int:
        return 76

    def to_string(self) -> str:
        return f"{self._name}: {self._body}"

    def get_body_as_string(self) -> str:
        return self._body


def test_a_header_of_an_application_is_written_as_it_writes_itself() -> None:
    headers = Headers(_WrittenElsewhere("X-Own", "as written"), _WrittenElsewhere("X-None", ""))

    assert headers.to_array() == ["X-Own: as written"]


def test_to_array() -> None:
    # Adapted: upstream's iso-8859-1 byte 0x8F is a C1 control as a character, refused here.
    value = "a" * 60 + "\xf8"
    headers = Headers().add_id_header("Message-ID", "some@id").add_text_header("Foo", value)

    message_id, foo = headers.to_array()

    # Adapted (D1): the Message-ID is plain ASCII and kept; Foo is decoded and compared.
    assert message_id == "Message-ID: <some@id>"
    assert_folded(foo)
    assert decode(foo) == value


def test_in_reply_to_accepts_non_identifier_values() -> None:
    headers = Headers().add_text_header("In-Reply-To", "foobar")

    assert header_of(headers, "In-Reply-To", UnstructuredHeader).get_body() == "foobar"


def test_in_reply_to_accepts_identifier_values() -> None:
    headers = Headers().add_id_header("In-Reply-To", "foo@bar.com")

    assert header_of(headers, "In-Reply-To", IdentificationHeader).get_body_as_string() == (
        "<foo@bar.com>"
    )


def test_references_accepts_non_identifier_values() -> None:
    headers = Headers().add_text_header("References", "foobar")

    assert header_of(headers, "References", UnstructuredHeader).get_body() == "foobar"


def test_references_accepts_identifier_values() -> None:
    headers = Headers().add_id_header("References", "foo@bar.com")

    assert header_of(headers, "References", IdentificationHeader).get_body_as_string() == (
        "<foo@bar.com>"
    )


def test_header_body() -> None:
    headers = Headers()
    assert headers.get_header_body("Content-Type") is None

    headers.set_header_body("text", "Content-Type", "type")

    assert headers.get_header_body("Content-Type") == "type"


def test_set_header_body_replaces_the_body_of_a_header_already_there() -> None:
    headers = Headers().add_text_header("Subject", "old")

    headers.set_header_body("text", "Subject", "new")

    assert headers.get_header_body("Subject") == "new"


def test_set_header_body_adds_a_header_of_each_kind() -> None:
    now = datetime.now(UTC)
    sender = Address("sender@example.com")
    path = Address("bounce@example.com")
    headers = Headers()

    headers.set_header_body("date", "Date", now)
    headers.set_header_body("mailbox", "Sender", sender)
    headers.set_header_body("path", "Return-Path", path)
    headers.set_header_body("mailbox_list", "To", [sender])
    headers.set_header_body("id", "Message-ID", "a@b")
    headers.set_header_body("parameterized", "Content-Disposition", "inline")

    assert headers.get_header_body("Date") == now
    assert headers.get_header_body("Sender") == sender
    assert headers.get_header_body("Return-Path") == path
    assert headers.get_header_body("To") == [sender]
    assert headers.get_header_body("Message-ID") == ["a@b"]
    assert headers.get_header_body("Content-Disposition") == "inline"


def test_header_parameter() -> None:
    headers = Headers()
    assert headers.get_header_parameter("Content-Disposition", "name") is None

    _ = headers.add_parameterized_header("Content-Disposition", "name")
    headers.set_header_parameter("Content-Disposition", "name", "foo")

    assert headers.get_header_parameter("Content-Disposition", "name") == "foo"


def test_a_header_parameter_cannot_be_set_on_a_missing_header() -> None:
    with pytest.raises(LogicError) as caught:
        Headers().set_header_parameter("Content-Disposition", "name", "foo")

    assert str(caught.value) == (
        'Unable to set parameter "name" on header "Content-Disposition" as the header is not '
        "defined."
    )


def test_a_header_parameter_cannot_be_set_on_a_header_that_is_not_parameterized() -> None:
    headers = Headers().add_text_header("Content-Disposition", "name")

    with pytest.raises(LogicError) as caught:
        headers.set_header_parameter("Content-Disposition", "name", "foo")

    assert str(caught.value) == (
        'Unable to set parameter "name" on header "Content-Disposition" as the header is not of '
        'class "xtr_mime.header.ParameterizedHeader".'
    )


def test_a_header_parameter_error_shows_the_names_escaped() -> None:
    with pytest.raises(LogicError) as caught:
        Headers().set_header_parameter("X-A\r\n", "na\x00me\ud800", "foo")

    assert str(caught.value) == (
        'Unable to set parameter "na\\x00me\\ud800" on header "X-A\\r\\n" as the header is not '
        "defined."
    )


def test_a_header_parameter_cannot_be_read_on_a_header_that_is_not_parameterized() -> None:
    headers = Headers().add_text_header("Content-Disposition", "name")

    with pytest.raises(LogicError) as caught:
        _ = headers.get_header_parameter("Content-Disposition", "name")

    assert str(caught.value) == (
        'Unable to get parameter "name" on header "Content-Disposition" as the header is not of '
        'class "xtr_mime.header.ParameterizedHeader".'
    )


def test_a_path_header_has_no_name() -> None:
    headers = Headers().add_path_header("Return-Path", Address("some@path", "any ignored name"))

    assert header_of(headers, "Return-Path", PathHeader).get_body_as_string() == "<some@path>"


INJECTED = "X-A\r\nX-Injected: value"

INJECTING_ADDERS: dict[str, Callable[[Headers], Headers]] = {
    "text": lambda h: h.add_text_header(INJECTED, "value"),
    "parameterized": lambda h: h.add_parameterized_header(INJECTED, "value", {"param": "foo"}),
    "mailbox_list": lambda h: h.add_mailbox_list_header(INJECTED, ["fabien@example.com"]),
    "mailbox": lambda h: h.add_mailbox_header(INJECTED, "fabien@example.com"),
    "path": lambda h: h.add_path_header(INJECTED, "fabien@example.com"),
    "date": lambda h: h.add_date_header(INJECTED, datetime.now(UTC)),
    "id": lambda h: h.add_id_header(INJECTED, "some@id"),
    "header": lambda h: h.add_header(INJECTED, "value"),
}


@pytest.mark.parametrize("add", INJECTING_ADDERS.values(), ids=INJECTING_ADDERS.keys())
def test_an_invalid_header_name_is_rejected(add: Callable[[Headers], Headers]) -> None:
    with pytest.raises(RfcComplianceError):
        _ = add(Headers())


def test_the_max_line_length_reaches_every_header_old_and_new() -> None:
    headers = Headers().add_text_header("Subject", "a")
    assert headers.get_max_line_length() == 76

    headers.set_max_line_length(78)
    _ = headers.add_text_header("X-Foo", "b")

    assert [header.get_max_line_length() for header in headers.all()] == [78, 78]


def test_a_header_named_with_a_colon_is_held_for_a_transport_but_never_rendered() -> None:
    headers = Headers().add_text_header("Bcc:victim@example.com,x", "value")

    assert headers.get_header_body("Bcc:victim@example.com,x") == "value"
    with pytest.raises(RfcComplianceError, match="colon"):
        _ = headers.to_string()
