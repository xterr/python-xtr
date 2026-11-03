"""An email: the builder of addresses, subject, priority, bodies and attachments.

Upstream's serialization cases (``serialize``, the unserialize guards on the charsets, the
attachment body kept in or out of the payload) are xtr-mailer's, which carries a queued email as
plain data and ports them through its queue; the serializer's normalizers have no counterpart.
Its case for the header assertion of the
test constraints belongs to the testing assertions. Upstream compares parts with object
equality; parts have none here (a multipart's boundary is random), so a tree is compared by its
shape.

The bodies an email builds are tested in ``test_email_body.py`` and
``test_email_related.py``, what it writes on the wire in ``test_email_wire.py``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import pytest

from tests.support.email_cases import NO_BODY, addressed_email
from xtr_mime import Address, Email, Group
from xtr_mime.exception import LogicError
from xtr_mime.header import MailboxListHeader
from xtr_mime.part import DataPart, TextPart

if TYPE_CHECKING:
    from collections.abc import Callable


def test_subject() -> None:
    email = Email().subject("Subject")

    assert email.get_subject() == "Subject"


def test_date() -> None:
    date = datetime.now(UTC)

    email = Email().date(date)

    assert email.get_date() == date


def test_return_path() -> None:
    email = Email().return_path("fabien@example.com")

    assert email.get_return_path() == Address("fabien@example.com")


def test_sender() -> None:
    email = Email().sender("fabien@example.com")
    assert email.get_sender() == Address("fabien@example.com")

    fabien = Address("fabien@example.com")
    _ = email.sender(fabien)
    assert email.get_sender() is fabien


def test_from_with_no_address() -> None:
    with pytest.raises(
        LogicError, match=r'^"from_\(\)" must be called with at least one address\.$'
    ):
        _ = Email().from_()


def _set(email: Email, kind: str, *addresses: Address | str) -> Email:
    setters: dict[str, Callable[..., Email]] = {
        "from": email.from_,
        "reply_to": email.reply_to,
        "to": email.to,
        "cc": email.cc,
        "bcc": email.bcc,
    }
    return setters[kind](*addresses)


def _add(email: Email, kind: str, *addresses: Address | str) -> Email:
    adders: dict[str, Callable[..., Email]] = {
        "from": email.add_from,
        "reply_to": email.add_reply_to,
        "to": email.add_to,
        "cc": email.add_cc,
        "bcc": email.add_bcc,
    }
    return adders[kind](*addresses)


def _get(email: Email, kind: str) -> list[Address]:
    getters: dict[str, Callable[[], list[Address]]] = {
        "from": email.get_from,
        "reply_to": email.get_reply_to,
        "to": email.get_to,
        "cc": email.get_cc,
        "bcc": email.get_bcc,
    }
    return getters[kind]()


ADDRESS_LISTS: Final = ["from", "reply_to", "to", "cc", "bcc"]


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_an_address_list_is_set_then_added_to(kind: str) -> None:
    email = Email()
    helene = Address("helene@example.com")
    thomas = Address("thomas@example.com", "Thomas")
    caramel = Address("caramel@example.com")

    assert _set(email, kind, "fabien@example.com", helene, thomas) is email
    assert _get(email, kind) == [Address("fabien@example.com"), helene, thomas]
    assert _get(email, kind)[1] is helene

    assert _add(email, kind, "lucas@example.com", caramel) is email
    got = _get(email, kind)
    assert got == [
        Address("fabien@example.com"),
        helene,
        thomas,
        Address("lucas@example.com"),
        caramel,
    ]
    assert got[4] is caramel


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_adding_to_an_address_list_not_set_creates_it(kind: str) -> None:
    email = _add(Email(), kind, "lucas@example.com", Address("caramel@example.com"))

    assert len(_get(email, kind)) == 2


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_setting_an_address_list_again_replaces_it(kind: str) -> None:
    caramel = Address("caramel@example.com")
    email = _set(Email(), kind, "lucas@example.com")

    _ = _set(email, kind, caramel)

    assert _get(email, kind) == [caramel]


@pytest.mark.parametrize("kind", ADDRESS_LISTS)
def test_an_address_list_not_set_is_empty(kind: str) -> None:
    assert _get(Email(), kind) == []


def test_to_with_an_empty_group() -> None:
    email = Email().from_("fabien@example.com").bcc("helene@example.com").text("content")
    group = Group("undisclosed-recipients")
    _ = email.get_headers().add_mailbox_list_header("To", [group])

    assert email.get_to() == []
    to = email.get_headers().get("To")
    assert isinstance(to, MailboxListHeader)
    assert to.get_address_list() == [group]
    assert to.to_string() == "To: undisclosed-recipients:;"
    email.ensure_validity()


def test_get_to_flattens_the_groups() -> None:
    email = Email().from_("fabien@example.com")
    chair = Address("chair@example.com")
    observer = Address("observer@example.com")
    _ = email.get_headers().add_mailbox_list_header("To", [Group("Board", [chair]), observer])

    assert email.get_to() == [chair, observer]
    to = email.get_headers().get("To")
    assert to is not None
    assert to.to_string() == "To: Board: chair@example.com;, observer@example.com"


def test_priority() -> None:
    email = Email()
    assert email.get_priority() == 3

    _ = email.priority(1)
    assert email.get_priority() == 1
    _ = email.priority(10)
    assert email.get_priority() == 5
    _ = email.priority(-10)
    assert email.get_priority() == 1


@pytest.mark.parametrize("value", ["12 (High)", "1" * 4301], ids=["two-digits", "many-digits"])
def test_a_priority_header_of_several_digits_reads_as_the_lowest(value: str) -> None:
    # Two digits from 1 to 5 make 11 or more: brought between 1 and 5, as priority() does.
    email = Email()
    _ = email.get_headers().add_text_header("X-Priority", value)

    assert email.get_priority() == 5


def test_priority_is_written_with_its_label() -> None:
    email = Email().priority(Email.PRIORITY_NORMAL)

    assert email.get_headers().get_header_body("X-Priority") == "3 (Normal)"


def test_priority_reads_the_leading_digits_of_the_header() -> None:
    email = Email()
    _ = email.get_headers().add_text_header("X-Priority", "2 (High)")

    assert email.get_priority() == 2


def test_invalid_body_with_empty_email() -> None:
    with pytest.raises(LogicError, match=f"^{re.escape(NO_BODY)}$"):
        Email().ensure_validity()


def _valid_recipients() -> Email:
    return Email().to("test@example.com").from_("test@example.com")


def test_body_with_text_is_valid() -> None:
    _valid_recipients().text("foo").ensure_validity()


def test_body_with_html_is_valid() -> None:
    _valid_recipients().html("foo").ensure_validity()


def test_empty_body_with_attachments_is_valid() -> None:
    _valid_recipients().add_part(DataPart("foo")).ensure_validity()


def test_set_body_is_valid() -> None:
    _valid_recipients().set_body(TextPart("foo")).ensure_validity()


def test_an_email_marked_as_unsent_is_not_valid() -> None:
    email = _valid_recipients().text("foo")
    _ = email.get_headers().add_text_header("X-Unsent", "1")

    with pytest.raises(LogicError, match=re.escape('Cannot send messages marked as "draft".')):
        email.ensure_validity()


def test_a_copy_has_attachments_of_its_own() -> None:
    email = addressed_email().text("foo")

    copied = email.__copy__()
    _ = copied.add_part(DataPart(b"bar")).subject("Copy")

    assert email.get_attachments() == []
    assert not email.get_headers().has("Subject")
