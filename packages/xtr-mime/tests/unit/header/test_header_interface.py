from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_mime import Address
from xtr_mime.header import (
    DateHeader,
    HeaderInterface,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    ParameterizedHeader,
    PathHeader,
    UnstructuredHeader,
)

HEADERS = [
    UnstructuredHeader("Subject", "Hello"),
    MailboxHeader("Sender", Address("a@example.com")),
    MailboxListHeader("To", [Address("a@example.com")]),
    DateHeader("Date", datetime(2000, 1, 1, tzinfo=UTC)),
    IdentificationHeader("Message-ID", "a@b"),
    ParameterizedHeader("Content-Type", "text/plain"),
    PathHeader("Return-Path", Address("a@example.com")),
]


@pytest.mark.parametrize("header", HEADERS, ids=[type(header).__name__ for header in HEADERS])
def test_every_header_class_is_a_header(header: object) -> None:
    assert isinstance(header, HeaderInterface)


def test_a_plain_object_is_not_a_header() -> None:
    assert not isinstance(object(), HeaderInterface)
