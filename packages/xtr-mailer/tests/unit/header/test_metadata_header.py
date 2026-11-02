"""A piece of metadata a provider keeps with the email and hands back in its events."""

from __future__ import annotations

import pytest
from xtr_mime import Headers, RfcComplianceError, UnstructuredHeader

from xtr_mailer.header import MetadataHeader


def test_the_key_names_the_header() -> None:
    header = MetadataHeader("Color", "blue")

    assert header.get_name() == "X-Metadata-Color"
    assert header.get_key() == "Color"
    assert header.get_value() == "blue"
    assert header.to_string() == "X-Metadata-Color: blue"


def test_it_is_a_text_header() -> None:
    assert isinstance(MetadataHeader("key", "value"), UnstructuredHeader)


def test_a_non_ascii_value_is_written_as_encoded_words() -> None:
    header = MetadataHeader("Name", "Hélène")

    assert header.get_body_as_string() != "Hélène"
    assert "?utf-8?" in header.get_body_as_string().lower()


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("a\r\nBcc: victim@example.com", id="crlf"),
        pytest.param("a b", id="space"),
        pytest.param("a\x00", id="null"),
        pytest.param("\udcff", id="surrogate"),
        pytest.param("é", id="non-ascii"),
        pytest.param("a:b", id="colon"),
    ],
)
def test_a_key_that_is_not_part_of_a_header_name_is_refused(key: str) -> None:
    with pytest.raises(RfcComplianceError) as raised:
        _ = Headers(MetadataHeader(key, "value")).to_string()

    message = str(raised.value)
    assert "\r" not in message
    assert "\n" not in message
    assert "\x00" not in message
    assert "\udcff" not in message


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a\r\nBcc: victim@example.com", id="crlf"),
        pytest.param("a\x00b", id="null"),
        pytest.param("a\udcffb", id="surrogate"),
    ],
)
def test_a_value_that_would_break_the_header_is_refused_when_written(value: str) -> None:
    with pytest.raises(RfcComplianceError) as raised:
        _ = MetadataHeader("key", value).to_string()

    assert value not in str(raised.value)


def test_a_huge_value_is_refused_without_being_repeated() -> None:
    with pytest.raises(RfcComplianceError) as raised:
        _ = MetadataHeader("key", "v" * 100_000).to_string()

    assert len(str(raised.value)) < 1_000
