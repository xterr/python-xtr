from __future__ import annotations

from tests.support.secret_header_request_parser import SecretHeaderRequestParser
from xtr_webhook.bundle import RouteConfig


def test_the_parser_defaults_to_none_meaning_the_bundles_own() -> None:
    assert RouteConfig().parser is None


def test_the_secret_defaults_to_an_empty_string() -> None:
    assert RouteConfig().secret == ""


def test_the_secret_stays_out_of_the_repr() -> None:
    assert "top-secret" not in repr(RouteConfig(secret="top-secret"))


def test_a_custom_parser_class_is_kept() -> None:
    assert RouteConfig(parser=SecretHeaderRequestParser).parser is SecretHeaderRequestParser
