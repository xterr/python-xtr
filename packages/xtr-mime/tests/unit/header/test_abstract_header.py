from __future__ import annotations

from typing import ClassVar

import pytest
from typing_extensions import override

from xtr_mime.exception import RfcComplianceError
from xtr_mime.header import AbstractHeader


class _TextHeader(AbstractHeader):
    """The smallest header there is: a fixed text body."""

    __slots__: ClassVar[tuple[str, ...]] = ("_text",)

    def __init__(self, name: str, text: str) -> None:
        super().__init__(name)
        self._text: str = text

    @override
    def get_body(self) -> str:
        return self._text

    @override
    def set_body(self, body: object) -> None:
        self._text = str(body)

    @override
    def _engine_value(self) -> str:
        return self._text


# UnstructuredHeaderTest::provideInvalidNames. Adapted: "X-\xc3\xa9" is "X-é" here, a str.
INVALID_NAMES = [
    "",
    "X-A\r\nX-Injected: value",
    "X-A\nX-Injected: value",
    "X-A\rX-Injected: value",
    "X-A: value\r\nX-Injected",
    "X A",
    "X-A\t",
    "X-\x00A",
    "X-\x7fA",
    "X-é",
]


@pytest.mark.parametrize("name", INVALID_NAMES)
def test_an_invalid_name_is_rejected(name: str) -> None:
    with pytest.raises(RfcComplianceError) as caught:
        _ = _TextHeader(name, "value")

    assert str(caught.value) == (
        f'The header name "{name}" contains characters that are not allowed in a header name.'
    )


@pytest.mark.parametrize(
    "name",
    [
        "Subject",
        "X-Custom-Header",
        "x-lower",
        "!#$%&'*+-.^_`|~",
        "Header-With-Digits-123",
        # Mailgun's API reads these prefixed names: a colon is printable ASCII too.
        "h:X-Mailgun-Tag",
        "o:tag",
        "h:Sender",
        "v:version",
        "t:text",
    ],
)
def test_valid_names_are_accepted(name: str) -> None:
    assert _TextHeader(name, "value").get_name() == name


def test_a_name_holding_a_colon_gives_its_body_to_a_transport_reading_fields() -> None:
    assert _TextHeader("h:X-Mailgun-Variables", '{"a":1}').get_body_as_string() == '{"a":1}'


@pytest.mark.parametrize("name", ["h:Sender", "Bcc:victim@example.com,x"])
def test_a_name_holding_a_colon_is_never_rendered_as_a_field(name: str) -> None:
    header = _TextHeader(name, "value")

    with pytest.raises(RfcComplianceError, match="colon"):
        _ = header.to_string()


def test_the_charset_defaults_to_utf_8_and_can_be_set() -> None:
    header = _TextHeader("Subject", "x")
    assert header.get_charset() == "utf-8"

    header.set_charset("iso-8859-1")

    assert header.get_charset() == "iso-8859-1"


def test_the_language_is_unset_until_set() -> None:
    header = _TextHeader("Subject", "x")
    assert header.get_language() is None

    header.set_language("en-us")

    assert header.get_language() == "en-us"


def test_the_max_line_length_defaults_to_76_and_can_be_set() -> None:
    header = _TextHeader("Subject", "x")
    assert header.get_max_line_length() == 76

    header.set_max_line_length(78)

    assert header.get_max_line_length() == 78


def test_to_string_is_the_field_the_engine_writes_without_its_line_break() -> None:
    assert _TextHeader("Subject", "Test").to_string() == "Subject: Test"


def test_the_body_as_string_is_the_field_without_its_name() -> None:
    assert _TextHeader("Subject", "Test").get_body_as_string() == "Test"


def test_a_value_the_engine_refuses_is_an_rfc_compliance_error() -> None:
    header = _TextHeader("Subject", "a\r\nBcc: evil@example.com")

    with pytest.raises(RfcComplianceError):
        _ = header.to_string()
