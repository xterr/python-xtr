"""Telling a submitted form by the media type its body is encoded in."""

from __future__ import annotations

import pytest

from xtr_security_http._form_content_type import is_form_content_type


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
