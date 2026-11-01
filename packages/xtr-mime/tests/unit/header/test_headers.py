from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, TypeVar, cast

import pytest

from tests.support.wire import assert_folded, decode
from xtr_mime import Address, Group
from xtr_mime.exception import InvalidArgumentError, LogicError, RfcComplianceError
from xtr_mime.header import (
    DateHeader,
    Headers,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    PathHeader,
    UnstructuredHeader,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_mime.header import HeaderInterface

T = TypeVar("T")


def _get(headers: Headers, name: str, header_class: type[T]) -> T:
    header = headers.get(name)
    assert isinstance(header, header_class)
    return header


def test_add_mailbox_list_header_delegates_to_the_factory() -> None:
    headers = Headers().add_mailbox_list_header("From", ["person@domain"])

    assert headers.get("From") is not None


def test_add_mailbox_list_header_takes_groups_and_strings() -> None:
    board = Group("Board", ["chair@example.com"])

    headers = Headers().add_mailbox_list_header("To", [board, "observer@example.com"])

    header = _get(headers, "To", MailboxListHeader)
    assert header.get_address_list() == [board, Address("observer@example.com")]
    assert header.to_string() == "To: Board: chair@example.com;, observer@example.com"


def test_add_header_takes_a_group() -> None:
    group = Group("undisclosed-recipients")

    headers = Headers().add_header("To", group)

    assert _get(headers, "To", MailboxListHeader).get_address_list() == [group]


def test_add_date_header_delegates_to_the_factory() -> None:
    headers = Headers().add_date_header("Date", datetime.now(UTC))

    assert headers.get("Date") is not None


def test_add_text_header_delegates_to_the_factory() -> None:
    assert Headers().add_text_header("Subject", "some text").get("Subject") is not None


def test_add_parameterized_header_delegates_to_the_factory() -> None:
    headers = Headers().add_parameterized_header("Content-Type", "text/plain", {"charset": "utf-8"})

    assert headers.get("Content-Type") is not None


def test_add_id_header_delegates_to_the_factory() -> None:
    assert Headers().add_id_header("Message-ID", "some@id").get("Message-ID") is not None


def test_add_path_header_delegates_to_the_factory() -> None:
    assert Headers().add_path_header("Return-Path", "some@path").get("Return-Path") is not None


def test_add_mailbox_header_delegates_to_the_factory() -> None:
    headers = Headers().add_mailbox_header("Sender", "Fabien <fabien@example.com>")

    assert _get(headers, "Sender", MailboxHeader).get_address() == Address(
        "fabien@example.com", "Fabien"
    )


def test_add_header_picks_the_class_from_the_name() -> None:
    now = datetime.now(UTC)
    headers = (
        Headers()
        .add_header("from", ["from@example.com"])
        .add_header("reply-to", "reply@example.com")
        .add_header("return-path", "return@example.com")
        .add_header("foo", "bar")
        .add_header("date", now)
        .add_header("message-id", "id@id")
        .add_header("sender", "sender@example.com")
    )

    assert _get(headers, "from", MailboxListHeader).get_body() == [Address("from@example.com")]
    assert _get(headers, "reply-to", MailboxListHeader).get_body() == [Address("reply@example.com")]
    assert _get(headers, "return-path", PathHeader).get_body() == Address("return@example.com")
    assert _get(headers, "foo", UnstructuredHeader).get_body() == "bar"
    assert _get(headers, "date", DateHeader).get_body() == now
    assert _get(headers, "message-id", IdentificationHeader).get_body() == ["id@id"]
    assert _get(headers, "sender", MailboxHeader).get_body() == Address("sender@example.com")


def test_add_header_takes_more_values_for_a_list_header() -> None:
    headers = (
        Headers()
        .add_header("To", "a@example.com", "b@example.com")
        .add_header("References", "ignored")
        .add_header("Message-ID", ["a@b"], "c@d")
    )

    assert _get(headers, "To", MailboxListHeader).get_body() == [
        Address("a@example.com"),
        Address("b@example.com"),
    ]
    assert _get(headers, "Message-ID", IdentificationHeader).get_ids() == ["a@b", "c@d"]


@pytest.mark.parametrize(
    ("name", "argument", "more"),
    [
        ("Subject", 42, ()),
        ("Subject", "a", ("b",)),
        ("Date", "yesterday", ()),
        ("Sender", 42, ()),
        ("Return-Path", 42, ()),
        ("To", 42, ()),
        ("Message-ID", 42, ()),
    ],
)
def test_add_header_refuses_a_value_its_class_does_not_take(
    name: str, argument: object, more: tuple[object, ...]
) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = Headers().add_header(name, argument, *more)


def test_has_returns_false_when_there_are_no_headers() -> None:
    assert not Headers().has("Some-Header")


ADDERS: list[tuple[str, Callable[[Headers], Headers]]] = [
    ("From", lambda h: h.add_mailbox_list_header("From", ["person@domain"])),
    ("Date", lambda h: h.add_date_header("Date", datetime.now(UTC))),
    ("Subject", lambda h: h.add_text_header("Subject", "some text")),
    ("Content-Type", lambda h: h.add_parameterized_header("Content-Type", "text/plain")),
    ("Message-ID", lambda h: h.add_id_header("Message-ID", "some@id")),
    ("Return-Path", lambda h: h.add_path_header("Return-Path", "some@path")),
    ("X-Foo", lambda h: h.add(UnstructuredHeader("X-Foo", "bar"))),
]


@pytest.mark.parametrize(("name", "add"), ADDERS)
def test_an_added_header_is_seen_by_has(name: str, add: Callable[[Headers], Headers]) -> None:
    assert add(Headers()).has(name)


def test_has_can_distinguish_multiple_headers() -> None:
    headers = Headers().add_text_header("X-Test", "some@id").add_text_header("X-Test", "other@id")

    assert headers.has("X-Test")


def test_get() -> None:
    header = IdentificationHeader("Message-ID", "some@id")

    headers = Headers().add_id_header("Message-ID", "some@id")

    assert _get(headers, "Message-ID", IdentificationHeader).to_string() == header.to_string()


def test_get_returns_none_if_the_header_is_not_set() -> None:
    assert Headers().get("Message-ID") is None


def _rendered(headers: list[HeaderInterface]) -> list[str]:
    return [header.to_string() for header in headers]


def test_all_returns_all_headers_matching_the_name() -> None:
    headers = Headers()
    for value in ["some@id", "other@id", "more@id"]:
        _ = headers.add_text_header("X-Test", value)

    # Adapted: headers compare by what they render; they are mutable, not values.
    assert _rendered(list(headers.all("X-Test"))) == [
        "X-Test: some@id",
        "X-Test: other@id",
        "X-Test: more@id",
    ]


def test_all_returns_all_headers_if_no_name_is_given() -> None:
    headers = (
        Headers()
        .add_id_header("Message-ID", "some@id")
        .add_text_header("Subject", "thing")
        .add_mailbox_list_header("To", [Address("person@example.org")])
    )

    assert _rendered(list(headers.all())) == [
        "Message-ID: <some@id>",
        "Subject: thing",
        "To: person@example.org",
    ]
    assert headers.get_names() == ["message-id", "subject", "to"]


def test_all_returns_nothing_if_none_is_set() -> None:
    assert list(Headers().all("Received")) == []


def test_remove_removes_all_headers_with_the_name() -> None:
    headers = Headers().add_id_header("X-Test", "some@id").add_id_header("X-Test", "other@id")

    headers.remove("X-Test")

    assert not headers.has("X-Test")


def test_has_is_not_case_sensitive() -> None:
    assert Headers().add_id_header("Message-ID", "some@id").has("message-id")


def test_get_is_not_case_sensitive() -> None:
    headers = Headers().add_id_header("Message-ID", "some@id")

    assert _get(headers, "message-id", IdentificationHeader).get_ids() == ["some@id"]


def test_all_is_not_case_sensitive() -> None:
    headers = Headers().add_id_header("Message-ID", "some@id")

    assert _rendered(list(headers.all("message-id"))) == ["Message-ID: <some@id>"]


def test_remove_is_not_case_sensitive() -> None:
    headers = Headers().add_id_header("Message-ID", "some@id")

    headers.remove("message-id")

    assert not headers.has("Message-ID")


def test_add_header_is_not_case_sensitive() -> None:
    headers = Headers().add_header("From", ["from@example.com"])

    assert _get(headers, "from", MailboxListHeader).get_body() == [Address("from@example.com")]


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

    assert _get(headers, "In-Reply-To", UnstructuredHeader).get_body() == "foobar"


def test_in_reply_to_accepts_identifier_values() -> None:
    headers = Headers().add_id_header("In-Reply-To", "foo@bar.com")

    assert _get(headers, "In-Reply-To", IdentificationHeader).get_body_as_string() == (
        "<foo@bar.com>"
    )


def test_references_accepts_non_identifier_values() -> None:
    headers = Headers().add_text_header("References", "foobar")

    assert _get(headers, "References", UnstructuredHeader).get_body() == "foobar"


def test_references_accepts_identifier_values() -> None:
    headers = Headers().add_id_header("References", "foo@bar.com")

    assert _get(headers, "References", IdentificationHeader).get_body_as_string() == (
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

    assert _get(headers, "Return-Path", PathHeader).get_body_as_string() == "<some@path>"


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


def test_a_copy_has_headers_of_its_own() -> None:
    headers = Headers().add_mailbox_list_header("To", ["a@example.com"])

    copied = copy.copy(headers)
    _get(copied, "To", MailboxListHeader).add_address(Address("b@example.com"))
    _ = copied.add_text_header("Subject", "copy only")

    assert _get(headers, "To", MailboxListHeader).get_body() == [Address("a@example.com")]
    assert not headers.has("Subject")


def test_a_header_given_to_the_constructor_is_added() -> None:
    header = cast("HeaderInterface", UnstructuredHeader("X-Foo", "bar"))

    assert Headers(header).get("x-foo") is header


def test_a_header_named_with_a_colon_is_held_for_a_transport_but_never_rendered() -> None:
    headers = Headers().add_text_header("Bcc:victim@example.com,x", "value")

    assert headers.get_header_body("Bcc:victim@example.com,x") == "value"
    with pytest.raises(RfcComplianceError, match="colon"):
        _ = headers.to_string()
