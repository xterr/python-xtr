"""A header collection: adding headers by kind, then finding and removing them by name.

What it refuses, and how it renders, is in ``test_headers_checks.py``.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

from tests.support.header_lookup import header_of
from xtr_mime import Address, Group
from xtr_mime.exception import InvalidArgumentError
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


def test_add_mailbox_list_header_delegates_to_the_factory() -> None:
    headers = Headers().add_mailbox_list_header("From", ["person@domain"])

    assert headers.get("From") is not None


def test_add_mailbox_list_header_takes_groups_and_strings() -> None:
    board = Group("Board", ["chair@example.com"])

    headers = Headers().add_mailbox_list_header("To", [board, "observer@example.com"])

    header = header_of(headers, "To", MailboxListHeader)
    assert header.get_address_list() == [board, Address("observer@example.com")]
    assert header.to_string() == "To: Board: chair@example.com;, observer@example.com"


def test_add_header_takes_a_group() -> None:
    group = Group("undisclosed-recipients")

    headers = Headers().add_header("To", group)

    assert header_of(headers, "To", MailboxListHeader).get_address_list() == [group]


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

    assert header_of(headers, "Sender", MailboxHeader).get_address() == Address(
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

    from_ = header_of(headers, "from", MailboxListHeader)
    assert from_.get_body() == [Address("from@example.com")]
    reply_to = header_of(headers, "reply-to", MailboxListHeader)
    assert reply_to.get_body() == [Address("reply@example.com")]
    return_path = header_of(headers, "return-path", PathHeader)
    assert return_path.get_body() == Address("return@example.com")
    assert header_of(headers, "foo", UnstructuredHeader).get_body() == "bar"
    assert header_of(headers, "date", DateHeader).get_body() == now
    assert header_of(headers, "message-id", IdentificationHeader).get_body() == ["id@id"]
    sender = header_of(headers, "sender", MailboxHeader)
    assert sender.get_body() == Address("sender@example.com")


def test_add_header_takes_more_values_for_a_list_header() -> None:
    headers = (
        Headers()
        .add_header("To", "a@example.com", "b@example.com")
        .add_header("References", "ignored")
        .add_header("Message-ID", ["a@b"], "c@d")
    )

    assert header_of(headers, "To", MailboxListHeader).get_body() == [
        Address("a@example.com"),
        Address("b@example.com"),
    ]
    assert header_of(headers, "Message-ID", IdentificationHeader).get_ids() == ["a@b", "c@d"]


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

    found = header_of(headers, "Message-ID", IdentificationHeader)
    assert found.to_string() == header.to_string()


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

    assert header_of(headers, "message-id", IdentificationHeader).get_ids() == ["some@id"]


def test_all_is_not_case_sensitive() -> None:
    headers = Headers().add_id_header("Message-ID", "some@id")

    assert _rendered(list(headers.all("message-id"))) == ["Message-ID: <some@id>"]


def test_remove_is_not_case_sensitive() -> None:
    headers = Headers().add_id_header("Message-ID", "some@id")

    headers.remove("message-id")

    assert not headers.has("Message-ID")


def test_add_header_is_not_case_sensitive() -> None:
    headers = Headers().add_header("From", ["from@example.com"])

    assert header_of(headers, "from", MailboxListHeader).get_body() == [Address("from@example.com")]


def test_a_copy_has_headers_of_its_own() -> None:
    headers = Headers().add_mailbox_list_header("To", ["a@example.com"])

    copied = copy.copy(headers)
    header_of(copied, "To", MailboxListHeader).add_address(Address("b@example.com"))
    _ = copied.add_text_header("Subject", "copy only")

    assert header_of(headers, "To", MailboxListHeader).get_body() == [Address("a@example.com")]
    assert not headers.has("Subject")


def test_a_header_given_to_the_constructor_is_added() -> None:
    header = cast("HeaderInterface", UnstructuredHeader("X-Foo", "bar"))

    assert Headers(header).get("x-foo") is header
