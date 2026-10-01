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
