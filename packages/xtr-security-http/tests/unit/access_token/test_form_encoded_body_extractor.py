"""The form extractor reads a token from a urlencoded request body."""

from __future__ import annotations

import pytest
from fastapi.security import HTTPBearer

from tests.support.messages import make_message
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.form_encoded_body_extractor import FormEncodedBodyExtractor

pytestmark = pytest.mark.anyio

_FORM_HEADERS = {"content-type": "application/x-www-form-urlencoded"}


def test_it_inherits_the_interface() -> None:
    assert AccessTokenExtractorInterface in FormEncodedBodyExtractor.__mro__


async def test_it_reads_a_form_field() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="POST",
        headers=_FORM_HEADERS,
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(request) == "f"
    assert isinstance(extractor.scheme(), HTTPBearer)


async def test_it_ignores_a_request_that_is_not_a_post() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="PUT",
        headers=_FORM_HEADERS,
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(request) is None


async def test_the_method_check_is_case_sensitive() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="post",
        headers=_FORM_HEADERS,
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(request) is None


async def test_it_ignores_a_non_form_body() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="POST",
        headers={"content-type": "application/json"},
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(request) is None


async def test_a_content_type_with_parameters_or_case_is_read() -> None:
    extractor = FormEncodedBodyExtractor()
    charset = make_message(
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded; charset=utf-8"},
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )
    mixed_case = make_message(
        method="POST",
        headers={"content-type": "Application/X-WWW-Form-Urlencoded"},
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(charset) == "f"
    assert await extractor.extract_access_token(mixed_case) == "f"


async def test_a_body_over_the_cap_yields_no_token_whatever_the_header_says() -> None:
    extractor = FormEncodedBodyExtractor()
    oversize = b"access_token=" + b"a" * (64 * 1024 + 1)

    honest = make_message(
        method="POST",
        headers={**_FORM_HEADERS, "content-length": str(len(oversize))},
        body=oversize,
        parsed_body={"access_token": "a" * (64 * 1024 + 1)},
    )
    lying = make_message(
        method="POST",
        headers={**_FORM_HEADERS, "content-length": "10"},
        body=oversize,
        parsed_body={"access_token": "a" * (64 * 1024 + 1)},
    )

    assert await extractor.extract_access_token(honest) is None
    assert await extractor.extract_access_token(lying) is None


async def test_a_body_at_the_cap_is_read() -> None:
    extractor = FormEncodedBodyExtractor()
    at_cap = b"access_token=" + b"a" * (64 * 1024 - len(b"access_token="))
    request = make_message(
        method="POST",
        headers=_FORM_HEADERS,
        body=at_cap,
        parsed_body={"access_token": "a" * (64 * 1024 - len(b"access_token="))},
    )

    assert await extractor.extract_access_token(request) == "a" * (
        64 * 1024 - len(b"access_token=")
    )


async def test_a_field_that_is_not_text_yields_no_token() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="POST",
        headers=_FORM_HEADERS,
        body=b"access_token=f&access_token=g",
        parsed_body={"access_token": ["f", "g"]},
    )

    assert await extractor.extract_access_token(request) is None


async def test_a_body_that_parsed_to_no_parameters_yields_no_token() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(method="POST", headers=_FORM_HEADERS, body=b"access_token=f")

    assert await extractor.extract_access_token(request) is None


async def test_the_body_is_read_before_the_form_is_answered_from() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_message(
        method="POST",
        headers=_FORM_HEADERS,
        body=b"access_token=f",
        parsed_body={"access_token": "f"},
    )

    assert await extractor.extract_access_token(request) == "f"

    # The extractor read the body: the stream it leaves behind is at its end,
    # the read that materialises a served request's parsed side.
    assert await request.get_body().read(1) == b""
