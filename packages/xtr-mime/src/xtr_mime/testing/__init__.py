"""Checks on the emails a test builds: their headers, subject, bodies and attachments.

Each check takes the message first and raises :class:`AssertionError` when the email is not
what the test expects, saying what was expected and, where it helps, what was found::

    email = Email().to("fabien@example.com").subject("Your order shipped").text("Hello")

    assert_email_header_same(email, "To", "fabien@example.com")
    assert_email_subject_contains(email, "order")
    assert_email_text_body_contains(email, "Hello")

A check asked about something a message cannot have — the headers of raw bytes, the subject
of a message that is not an :class:`~xtr_mime.Email` — raises
:class:`~xtr_mime.exception.LogicError` instead: the test is wrong, not the email.

Nothing here needs a test framework, and the package itself never imports this module.
"""

from __future__ import annotations

from ._body_assertions import (
    assert_email_attachment_count,
    assert_email_html_body_contains,
    assert_email_html_body_not_contains,
    assert_email_subject_contains,
    assert_email_subject_not_contains,
    assert_email_text_body_contains,
    assert_email_text_body_not_contains,
)
from ._header_assertions import (
    assert_email_address_contains,
    assert_email_has_header,
    assert_email_header_not_same,
    assert_email_header_same,
    assert_email_not_has_header,
)

__all__ = [
    "assert_email_address_contains",
    "assert_email_attachment_count",
    "assert_email_has_header",
    "assert_email_header_not_same",
    "assert_email_header_same",
    "assert_email_html_body_contains",
    "assert_email_html_body_not_contains",
    "assert_email_not_has_header",
    "assert_email_subject_contains",
    "assert_email_subject_not_contains",
    "assert_email_text_body_contains",
    "assert_email_text_body_not_contains",
]
