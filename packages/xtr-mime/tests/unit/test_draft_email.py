"""A draft: an email a mail client finishes, so it needs no sender, date or identifier."""

from __future__ import annotations

import re

import pytest

from xtr_mime import DraftEmail
from xtr_mime.exception import LogicError


def test_can_have_just_body() -> None:
    rendered = DraftEmail().text("some text").to_string()

    assert "some text" in rendered
    assert "MIME-Version: 1.0" in rendered
    assert "X-Unsent: 1" in rendered


def test_bcc_is_removed() -> None:
    rendered = DraftEmail().text("some text").bcc("sam@example.com").to_string()

    assert "sam@example.com" not in rendered


def test_must_have_body() -> None:
    with pytest.raises(LogicError):
        _ = DraftEmail().to_string()


def test_ensure_validity_always_fails() -> None:
    email = DraftEmail().to("alice@example.com").from_("webmaster@example.com").text("some text")

    with pytest.raises(LogicError, match=re.escape('Cannot send messages marked as "draft".')):
        email.ensure_validity()


def test_prepared_headers_add_no_sender_date_or_identifier() -> None:
    headers = DraftEmail().text("some text").get_prepared_headers()

    assert headers.get_names() == ["x-unsent", "mime-version"]


def test_prepared_headers_keep_a_mime_version_set() -> None:
    email = DraftEmail()
    _ = email.get_headers().add_text_header("MIME-Version", "1.0")

    versions = [header.get_body() for header in email.get_prepared_headers().all("MIME-Version")]

    assert versions == ["1.0"]
