"""Headers as a queued email carries them: each of its class, and its name checked on the way in."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from xtr_mime import Address, Group, Headers, UnstructuredHeader
from xtr_mime.header import FoldedHeader

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.header import MetadataHeader, TagHeader, TrackingHeader
from xtr_mailer.messenger._wire._headers import read_headers, write_headers

_TEXT_HEADER = {"$type": "text", "name": "X-A", "charset": "utf-8", "language": None, "value": "v"}


def _back(headers: Headers) -> Headers:
    return read_headers(write_headers(headers), "headers")


def _headers() -> Headers:
    headers = (
        Headers()
        .add_mailbox_list_header("From", [Address("a@example.com", "Ä"), "b@example.com"])
        .add_mailbox_list_header("To", [Group("Team", ["c@example.com"]), "d@example.com"])
        .add_mailbox_header("Sender", Address("s@example.com", "S"))
        .add_text_header("Subject", "Über alles")
        .add_date_header(
            "Date", datetime(2026, 11, 3, 9, 30, 15, 120, timezone(timedelta(hours=2)))
        )
        .add_id_header("Message-ID", "abc@example.com")
        .add_id_header("References", ["a@example.com", "b@example.com"])
        .add_path_header("Return-Path", "bounces@example.com")
        .add_parameterized_header("X-P", "value", {"a": "1", "b": None})
        .add(TagHeader("password-reset"))
        .add(MetadataHeader("Color", "blue"))
        .add(TrackingHeader(opens=True, clicks=None))
        .add(FoldedHeader("DKIM-Signature: v=1; a=rsa-sha256;\r\n b=abc"))
    )
    subject = headers.get("Subject")
    assert subject is not None
    subject.set_language("de")
    return headers


def test_every_header_comes_back_of_its_class_with_its_name_and_value() -> None:
    headers = _headers()

    back = _back(headers)

    assert [(type(h), h.get_name()) for h in back.all()] == [
        (type(h), h.get_name()) for h in headers.all()
    ]
    assert back.to_array() == headers.to_array()


def test_a_header_keeps_its_charset_and_language() -> None:
    back = _back(_headers()).get("Subject")

    assert back is not None
    assert (back.get_charset(), back.get_language()) == ("utf-8", "de")


def test_the_line_length_comes_back() -> None:
    headers = Headers(UnstructuredHeader("X-A", "v"))
    headers.set_max_line_length(50)

    assert _back(headers).get_max_line_length() == 50


def test_a_date_keeps_its_offset_and_microseconds() -> None:
    date = datetime(2026, 11, 3, 9, 30, 15, 120, tzinfo=UTC)

    back = _back(Headers().add_date_header("Date", date)).get_header_body("Date")

    assert back == date


def test_the_tracking_and_metadata_headers_keep_what_they_say() -> None:
    back = _back(_headers())

    tracking, metadata = back.get("X-Track"), back.get("X-Metadata-Color")
    assert isinstance(tracking, TrackingHeader)
    assert (tracking.get_opens(), tracking.get_clicks()) == (True, None)
    assert isinstance(metadata, MetadataHeader)
    assert (metadata.get_key(), metadata.get_value()) == ("Color", "blue")


def test_the_folded_header_is_written_as_it_was_folded() -> None:
    back = _back(_headers()).get("DKIM-Signature")

    assert isinstance(back, FoldedHeader)
    assert back.to_string() == "DKIM-Signature: v=1; a=rsa-sha256;\r\n b=abc"


def test_a_header_of_a_class_the_queue_does_not_know_is_refused_when_written() -> None:
    class _Custom(UnstructuredHeader):
        pass

    with pytest.raises(InvalidArgumentError, match="_Custom"):
        _ = write_headers(Headers(_Custom("X-A", "v")))


def _fields(*entries: object) -> dict[str, object]:
    return {"line_length": 76, "fields": list(entries)}


@pytest.mark.parametrize(
    "name",
    ["X-A\r\nBcc: victim@example.com", "X-A\x00", "", "X " + "A" * 10, "A" * 10_000, 3],
    ids=["line break", "null", "empty", "space", "long", "number"],
)
def test_a_name_that_is_no_header_name_is_refused_before_it_is_built(name: object) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_headers(_fields({**_TEXT_HEADER, "name": name}), "headers")

    message = str(raised.value)
    assert message.startswith("The queued email cannot be read: headers.fields[0].name ")
    assert "victim" not in message
    assert "AAAA" not in message


def test_a_header_of_a_kind_the_queue_does_not_know_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match=r"headers.fields\[0\] is not a header"):
        _ = read_headers(_fields({**_TEXT_HEADER, "$type": "x-evil"}), "headers")


def test_a_header_its_class_refuses_is_refused() -> None:
    entry = {**_TEXT_HEADER, "$type": "id", "ids": ["no identifier"]}
    _ = entry.pop("value")

    with pytest.raises(InvalidArgumentError, match=r"headers.fields\[0\] is not a header"):
        _ = read_headers(_fields(entry), "headers")


def test_a_header_breaking_the_rules_of_headers_is_refused() -> None:
    entry = {**_TEXT_HEADER, "name": "From"}

    with pytest.raises(InvalidArgumentError, match=r"headers.fields\[0\] is not a header"):
        _ = read_headers(_fields(entry), "headers")


def test_a_folded_header_that_would_start_another_is_refused() -> None:
    entry = {"$type": "folded", "name": "X-A", "charset": "utf-8", "language": None}

    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_headers(_fields({**entry, "field": "X-A: a\r\nBcc: victim@x"}), "headers")

    assert "victim" not in str(raised.value)


def test_a_folded_header_named_otherwise_than_its_field_is_refused() -> None:
    entry = {"$type": "folded", "name": "X-B", "charset": "utf-8", "language": None}

    with pytest.raises(InvalidArgumentError):
        _ = read_headers(_fields({**entry, "field": "X-A: a"}), "headers")


def test_a_tag_header_under_another_name_is_refused() -> None:
    entry = {**_TEXT_HEADER, "$type": "tag", "name": "X-Other"}

    with pytest.raises(InvalidArgumentError):
        _ = read_headers(_fields(entry), "headers")


def test_a_tracking_flag_that_is_no_boolean_is_refused() -> None:
    entry = {**_TEXT_HEADER, "$type": "tracking", "name": "X-Track", "opens": "yes"}

    with pytest.raises(InvalidArgumentError, match=r"fields\[0\]\.opens is not true"):
        _ = read_headers(_fields({**entry, "clicks": None}), "headers")
