"""DKIM options remember what was set, and only that: the rest is the signer's to decide."""

from __future__ import annotations

from xtr_mime.crypto import DkimOptions


def test_nothing_is_set_on_new_options() -> None:
    options = DkimOptions()

    assert options.get_algorithm() is None
    assert options.get_body_show_length() is None
    assert options.get_header_canon() is None
    assert options.get_body_canon() is None
    assert options.get_headers_to_ignore() is None


def test_each_option_set_is_returned() -> None:
    options = (
        DkimOptions()
        .algorithm("rsa-sha256")
        .body_show_length(False)
        .header_canon("simple")
        .body_canon("relaxed")
        .headers_to_ignore(["Message-ID", "X-Mailer"])
    )

    assert options.get_algorithm() == "rsa-sha256"
    assert options.get_body_show_length() is False
    assert options.get_header_canon() == "simple"
    assert options.get_body_canon() == "relaxed"
    assert options.get_headers_to_ignore() == ("Message-ID", "X-Mailer")


def test_the_headers_to_ignore_are_copied() -> None:
    names = ["Message-ID"]
    options = DkimOptions().headers_to_ignore(names)

    names.append("Subject")

    assert options.get_headers_to_ignore() == ("Message-ID",)


def test_setting_an_option_returns_the_same_options() -> None:
    options = DkimOptions()

    assert options.algorithm("rsa-sha256") is options
