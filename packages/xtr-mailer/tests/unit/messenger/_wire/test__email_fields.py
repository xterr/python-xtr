"""What an email builds its body from, and the template of one a provider renders, on the queue."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING, cast

import pytest
from xtr_mime import DataPart, Email, TextPart

from xtr_mailer import RemoteTemplateEmail
from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._email_fields import (
    EMAIL_FIELDS,
    TEMPLATE_FIELD,
    read_email_fields,
    write_email_fields,
)
from xtr_mailer.messenger._wire._parts import read_leaf, write_leaf

if TYPE_CHECKING:
    from xtr_mime import AbstractPart

    from xtr_mailer.messenger._wire import JsonObject


def _write_part(part: AbstractPart) -> JsonObject:
    written = write_leaf(part)
    assert written is not None
    return written


def _written(email: Email) -> JsonObject:
    return write_email_fields(email, _write_part)


def _read(found: JsonObject, email: Email | None = None) -> Email:
    read = Email() if email is None else email
    read_email_fields(read, found, "message", read_leaf)
    return read


def test_the_text_and_html_come_back_as_they_were_given_with_their_charsets() -> None:
    email = Email().text("été", "iso-8859-1").html(b"<p>hi</p>", "utf-16")

    back = _read(_written(email))

    assert (back.get_text_body(), back.get_text_charset()) == ("été", "iso-8859-1")
    assert (back.get_html_body(), back.get_html_charset()) == (b"<p>hi</p>", "utf-16")


def test_a_stream_is_read_from_its_start_when_it_is_written() -> None:
    stream = io.BytesIO(b"from the start")
    _ = stream.read(5)

    written = _written(Email().text(stream))

    assert written["text"] == {"bytes": "ZnJvbSB0aGUgc3RhcnQ="}


def test_an_email_without_a_body_writes_none_for_each() -> None:
    written = _written(Email())

    assert tuple(written) == EMAIL_FIELDS
    assert (written["text"], written["html"], written["attachments"]) == (None, None, [])


def test_the_attachments_come_back_in_order() -> None:
    email = Email().add_part(DataPart(b"a", "a.txt")).add_part(DataPart(b"b", "b.txt"))

    back = _read(_written(email))

    assert [part.get_filename() for part in back.get_attachments()] == ["a.txt", "b.txt"]


def test_a_part_that_is_no_attachment_is_refused() -> None:
    written = {**_written(Email()), "attachments": [_write_part(TextPart("not attached"))]}

    with pytest.raises(InvalidArgumentError, match=r"message\.attachments\[0\] is not an attach"):
        _ = _read(written)


def test_a_body_without_a_charset_is_refused() -> None:
    written = {**_written(Email().text("t")), "text_charset": None}

    with pytest.raises(InvalidArgumentError, match=r"message\.text_charset is null where a body"):
        _ = _read(written)


def test_a_charset_longer_than_a_charset_name_is_refused() -> None:
    written = {**_written(Email().text("t")), "text_charset": "c" * 65}

    with pytest.raises(InvalidArgumentError, match=r"message\.text_charset is longer"):
        _ = _read(written)


def test_an_email_not_rendered_from_a_template_writes_no_template_field() -> None:
    assert TEMPLATE_FIELD not in _written(Email())


def test_the_template_comes_back_with_its_variables() -> None:
    email = RemoteTemplateEmail().template("welcome", {"name": "Ana", "count": 2})

    back = cast("RemoteTemplateEmail", _read(_written(email), RemoteTemplateEmail()))

    template = back.get_remote_template()
    assert template is not None
    assert (template.get_reference(), template.get_variables()) == (
        "welcome",
        {"name": "Ana", "count": 2},
    )


def test_no_template_stays_none() -> None:
    written = _written(RemoteTemplateEmail())

    back = cast("RemoteTemplateEmail", _read(written, RemoteTemplateEmail()))

    assert (written[TEMPLATE_FIELD], back.get_remote_template()) == (None, None)


@pytest.mark.parametrize(
    ("template", "where"),
    [
        ("welcome", r"message\.template is not an object"),
        ({"reference": "welcome"}, r"message\.template does not hold"),
        ({"reference": 3, "variables": {}}, r"message\.template\.reference is not text"),
        ({"reference": "welcome", "variables": []}, r"message\.template\.variables is not an"),
    ],
    ids=["text", "no variables", "number reference", "list variables"],
)
def test_a_template_of_the_wrong_shape_is_refused(template: object, where: str) -> None:
    written = {**_written(RemoteTemplateEmail().template("welcome")), TEMPLATE_FIELD: template}

    with pytest.raises(InvalidArgumentError, match=where):
        _ = _read(written, RemoteTemplateEmail())
