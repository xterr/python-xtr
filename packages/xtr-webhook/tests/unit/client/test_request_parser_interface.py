from __future__ import annotations

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.client import RequestParserInterface


def test_a_parser_is_recognised_at_runtime() -> None:
    assert isinstance(SecretHeaderRequestParser(), RequestParserInterface)


def test_something_that_cannot_parse_is_not() -> None:
    assert not isinstance(object(), RequestParserInterface)
