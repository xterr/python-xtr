"""The form extractor reads a token from a urlencoded request body."""

from __future__ import annotations

import pytest
from fastapi.security import HTTPBearer

from tests.support.requests import make_request
from xtr_security_http.access_token.access_token_extractor_interface import (
    AccessTokenExtractorInterface,
)
from xtr_security_http.access_token.form_encoded_body_extractor import FormEncodedBodyExtractor

pytestmark = pytest.mark.anyio


def test_it_inherits_the_interface() -> None:
    assert AccessTokenExtractorInterface in FormEncodedBodyExtractor.__mro__


async def test_it_reads_a_form_field() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"access_token=f",
    )

    assert await extractor.extract_access_token(request) == "f"
    assert isinstance(extractor.scheme(), HTTPBearer)


async def test_it_ignores_a_non_form_body() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(method="POST", headers={"content-type": "application/json"})

    assert await extractor.extract_access_token(request) is None


async def test_it_ignores_a_body_whose_declared_length_is_over_the_cap() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "content-length": str(64 * 1024 + 1),
        },
        body=b"access_token=f",
    )

    assert await extractor.extract_access_token(request) is None


async def test_it_ignores_a_streamed_body_over_the_cap() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"access_token=" + b"a" * (64 * 1024 + 1),
    )

    assert await extractor.extract_access_token(request) is None


@pytest.mark.parametrize("declared", ["-1", " 10 ", "+5", "10,10", "0x10", ""])
async def test_a_body_whose_declared_length_is_not_a_plain_number_is_read_capped(
    declared: str,
) -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "content-length": declared,
        },
        body=b"access_token=" + b"a" * (64 * 1024 + 1),
    )

    assert await extractor.extract_access_token(request) is None


@pytest.mark.parametrize("declared", ["-1", " 10 ", "+5", "10,10", "0x10", ""])
async def test_a_small_body_is_read_despite_an_unparsable_declared_length(
    declared: str,
) -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={
            "content-type": "application/x-www-form-urlencoded",
            "content-length": declared,
        },
        body=b"access_token=f",
    )

    assert await extractor.extract_access_token(request) == "f"


async def test_it_ignores_a_non_utf8_body() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"access_token=\xff\xfe",
    )

    assert await extractor.extract_access_token(request) is None


async def test_a_streamed_body_is_left_readable_for_the_route() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"access_token=f&title=Dune",
    )

    assert await extractor.extract_access_token(request) == "f"
    assert await request.body() == b"access_token=f&title=Dune"


async def test_a_content_type_with_mixed_case_is_read() -> None:
    extractor = FormEncodedBodyExtractor()
    request = make_request(
        method="POST",
        headers={"content-type": "Application/X-WWW-Form-Urlencoded"},
        body=b"access_token=f",
    )

    assert await extractor.extract_access_token(request) == "f"
