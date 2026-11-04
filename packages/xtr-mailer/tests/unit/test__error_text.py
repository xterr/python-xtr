"""What was given, shown in an error message without breaking it."""

from __future__ import annotations

import pytest
from xtr_mime import Message, RawMessage
from xtr_mime.part import DataPart

from tests.support.fake_transport import FakeTransport
from xtr_mailer._error_text import shown, type_name
from xtr_mailer.transport import NullTransport, Transports


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("fabièn@example.com", "fabièn@example.com", id="printable"),
        pytest.param("a\r\nb", "a\\r\\nb", id="line-break"),
        pytest.param("a\x00b", "a\\x00b", id="null"),
        pytest.param("a\udcffb", "a\\udcffb", id="surrogate"),
        pytest.param('a"b', 'a"b', id="quote"),
        pytest.param("a'b", "a'b", id="apostrophe"),
        pytest.param("é" * 64, "é" * 64, id="at-the-limit"),
        pytest.param("é" * 65, "é" * 64 + "…", id="over-the-limit"),
    ],
)
def test_a_value_is_shown_escaped_and_cut_short(value: str, expected: str) -> None:
    assert shown(value) == expected


def test_a_mailer_class_is_named_by_the_package_it_is_imported_from() -> None:
    assert type_name(Transports) == "xtr_mailer.transport.Transports"
    assert type_name(NullTransport) == "xtr_mailer.transport.NullTransport"


def test_a_mime_class_is_named_by_the_package_it_is_imported_from() -> None:
    assert type_name(RawMessage) == "xtr_mime.RawMessage"
    assert type_name(Message) == "xtr_mime.Message"
    assert type_name(DataPart) == "xtr_mime.part.DataPart"


def test_any_other_class_is_named_by_its_module() -> None:
    assert type_name(FakeTransport) == "tests.support.fake_transport.FakeTransport"
