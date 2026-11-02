"""The open and click tracking an email asks its provider for."""

from __future__ import annotations

import pytest
from xtr_mime import Address, Headers, MailboxHeader, RfcComplianceError, UnstructuredHeader

from xtr_mailer.header import TrackingHeader


def test_both_flags_default_to_none() -> None:
    header = TrackingHeader()

    assert header.get_name() == "X-Track"
    assert header.get_opens() is None
    assert header.get_clicks() is None
    assert header.to_string() == "X-Track: opens=default; clicks=default"


def test_the_flags_are_kept_and_written() -> None:
    header = TrackingHeader(opens=True, clicks=False)

    assert header.get_opens() is True
    assert header.get_clicks() is False
    assert header.to_string() == "X-Track: opens=true; clicks=false"


def test_it_is_a_text_header() -> None:
    assert isinstance(TrackingHeader(), UnstructuredHeader)
    assert TrackingHeader.NAME == "X-Track"


def test_from_headers_finds_none_without_the_header() -> None:
    assert TrackingHeader.from_headers(Headers()) is None


def test_from_headers_returns_the_header_itself() -> None:
    header = TrackingHeader(opens=True)

    assert TrackingHeader.from_headers(Headers(header)) is header


def test_from_headers_reads_a_text_header() -> None:
    headers = Headers().add_text_header("X-Track", "opens=false; clicks=default")

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert header.get_opens() is False
    assert header.get_clicks() is None


def test_from_headers_reads_the_name_whatever_its_case() -> None:
    headers = Headers().add_text_header("x-track", " clicks=true ;opens= true")

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert header.get_opens() is True
    assert header.get_clicks() is True


def test_from_headers_reads_no_key_with_spaces_before_its_equals_sign() -> None:
    headers = Headers().add_text_header("X-Track", "opens =true")

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert header.get_opens() is None


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("yes please", id="no-flag"),
        pytest.param("opens=yes; clicks=", id="unknown-values"),
        pytest.param("sends=true; opens", id="unknown-key-and-no-value"),
        pytest.param("opens=true\r\nBcc: victim@example.com", id="line-break"),
        pytest.param("opens=\x00true; clicks=\udcff", id="null-and-surrogate"),
        pytest.param("opens=true;" * 10_000, id="huge"),
    ],
)
def test_from_headers_tolerates_malformed_values(value: str) -> None:
    headers = Headers().add_text_header("X-Track", value)

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert header.to_string().startswith("X-Track: opens=")
    assert header.get_clicks() is None


def test_from_headers_reads_a_huge_value_by_its_last_flag() -> None:
    headers = Headers().add_text_header("X-Track", "opens=false;" * 10_000 + "opens=true")

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert header.get_opens() is True


def test_from_headers_tolerates_a_header_that_is_not_text() -> None:
    headers = Headers(MailboxHeader("X-Track", Address("opens@example.com")))

    header = TrackingHeader.from_headers(headers)

    assert header is not None
    assert (header.get_opens(), header.get_clicks()) == (None, None)


def test_a_tracking_header_with_a_line_break_set_is_refused_when_written() -> None:
    header = TrackingHeader()
    header.set_value("opens=true\r\nBcc: victim@example.com")

    with pytest.raises(RfcComplianceError):
        _ = header.to_string()
