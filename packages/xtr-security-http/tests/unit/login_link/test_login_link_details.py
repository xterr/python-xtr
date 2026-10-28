"""The details of one minted login link: its URL and its moment."""

from __future__ import annotations

from datetime import UTC, datetime

from xtr_security_http.login_link import LoginLinkDetails


def test_get_url_returns_the_link_whole() -> None:
    details = LoginLinkDetails("/login-link?user=ada", datetime(2024, 4, 9, 12, tzinfo=UTC))

    assert details.get_url() == "/login-link?user=ada"


def test_get_expires_at_returns_the_moment_the_link_stops_counting() -> None:
    expires_at = datetime(2024, 4, 9, 12, 10, tzinfo=UTC)
    details = LoginLinkDetails("/login-link?user=ada", expires_at)

    assert details.get_expires_at() is expires_at


def test_the_link_is_where_it_leads() -> None:
    details = LoginLinkDetails("/login-link?user=ada", datetime(2024, 4, 9, 12, tzinfo=UTC))

    assert str(details) == "/login-link?user=ada"
