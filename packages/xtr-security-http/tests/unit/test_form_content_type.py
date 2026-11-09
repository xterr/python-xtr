"""Telling a submitted form by the media type its body is encoded in."""

from __future__ import annotations

import pytest

from xtr_security_http._form_content_type import is_form_content_type

_URLENCODED_ONLY = frozenset({"application/x-www-form-urlencoded"})


@pytest.mark.parametrize(
    "content_type",
    [
        "application/x-www-form-urlencoded",
        "multipart/form-data; boundary=b",
        "Application/X-WWW-Form-Urlencoded; charset=UTF-8",
        " multipart/form-data ",
    ],
)
def test_a_form_encoding_names_a_form(content_type: str) -> None:
    assert is_form_content_type(content_type) is True


@pytest.mark.parametrize(
    "content_type",
    [
        "application/x-www-form-urlencodedX",
        "multipart/form-dataX; boundary=b",
        "application/json",
        "",
    ],
)
def test_a_media_type_that_only_starts_like_a_form_encoding_names_no_form(
    content_type: str,
) -> None:
    assert is_form_content_type(content_type) is False


def test_a_form_encoding_left_out_of_the_media_types_asked_for_names_no_form() -> None:
    content_type = "multipart/form-data; boundary=b"

    assert is_form_content_type(content_type, media_types=_URLENCODED_ONLY) is False


def test_the_media_types_asked_for_are_weighed_by_the_same_rule() -> None:
    content_type = "Application/X-WWW-Form-Urlencoded; charset=UTF-8"

    assert is_form_content_type(content_type, media_types=_URLENCODED_ONLY) is True
