from __future__ import annotations

import pytest

from xtr_http_client.data_collector._masking import (
    MASK,
    masked,
    masked_header_line,
    sensitive_field,
    sensitive_header,
)


@pytest.mark.parametrize(
    "name", ["password", "client_secret", "accessToken", "PASSWD", "api_key", "ApiKey"]
)
def test_a_field_named_like_a_credential_is_sensitive(name: str) -> None:
    assert sensitive_field(name)


def test_an_ordinary_field_is_not_sensitive() -> None:
    assert not sensitive_field("username")


@pytest.mark.parametrize(
    "name",
    ["Authorization", "proxy-authorization", "Cookie", "Set-Cookie", "X-Api-Key", "X-Auth-Token"],
)
def test_a_credential_header_is_sensitive(name: str) -> None:
    assert sensitive_header(name)


def test_an_ordinary_header_is_not_sensitive() -> None:
    assert not sensitive_header("Accept")


def test_a_credential_header_line_keeps_its_name_and_loses_its_value() -> None:
    assert masked_header_line("Set-Cookie: session=abc") == f"Set-Cookie: {MASK}"


def test_an_ordinary_header_line_is_kept_as_it_is() -> None:
    assert masked_header_line("Content-Type: text/plain") == "Content-Type: text/plain"


def test_a_status_line_is_kept_as_it_is() -> None:
    assert masked_header_line("HTTP/1.1 200 OK") == "HTTP/1.1 200 OK"


def test_credentials_are_masked_however_deep() -> None:
    value = {"user": "ann", "password": "pw", "nested": [{"token": "t", "id": 7}], "pair": (1,)}

    assert masked(value) == {
        "user": "ann",
        "password": MASK,
        "nested": [{"token": MASK, "id": 7}],
        "pair": [1],
    }


def test_a_value_that_holds_no_fields_is_kept_as_it_is() -> None:
    assert masked(b"raw") == b"raw"
