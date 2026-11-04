"""A tag a provider files the email under."""

from __future__ import annotations

import pytest
from xtr_mime import Email, Headers, RfcComplianceError, UnstructuredHeader

from xtr_mailer.header import TagHeader


def test_the_tag_is_written_as_x_tag() -> None:
    header = TagHeader("password-reset")

    assert header.get_name() == "X-Tag"
    assert header.get_value() == "password-reset"
    assert header.to_string() == "X-Tag: password-reset"


def test_it_is_a_text_header() -> None:
    assert isinstance(TagHeader("tag"), UnstructuredHeader)


def test_an_email_carries_several_tags() -> None:
    email = Email().from_("fabien@example.com").to("helene@example.com").text("text")
    _ = email.get_headers().add(TagHeader("one")).add(TagHeader("two"))

    rendered = email.to_string()

    assert "X-Tag: one\r\n" in rendered
    assert "X-Tag: two\r\n" in rendered


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("a\r\nBcc: victim@example.com", id="crlf"),
        pytest.param("a\nb", id="lf"),
        pytest.param("a\x00b", id="null"),
        pytest.param("a\udcffb", id="surrogate"),
    ],
)
def test_a_tag_that_would_break_the_header_is_refused_when_written(value: str) -> None:
    headers = Headers(TagHeader(value))

    with pytest.raises(RfcComplianceError) as raised:
        _ = headers.to_string()

    assert value not in str(raised.value)


def test_a_huge_tag_is_refused_without_being_repeated() -> None:
    value = "x" * 100_000

    with pytest.raises(RfcComplianceError) as raised:
        _ = TagHeader(value).to_string()

    assert len(str(raised.value)) < 1_000
