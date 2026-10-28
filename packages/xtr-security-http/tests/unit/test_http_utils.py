"""The HTTP utilities: path checks, URI generation and redirect responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_kernel.bridge import ResponseFactory
from xtr_security_core.exception import InvalidArgumentError

from tests.support.messages import make_message
from xtr_security_http.http_utils import HttpUtils

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


def _utils(
    *,
    uri_builder: Callable[[str], str] | None = None,
    domain_regexp: str | None = None,
    secure_domain_regexp: str | None = None,
) -> HttpUtils:
    return HttpUtils(
        ResponseFactory(),
        uri_builder,
        domain_regexp,
        secure_domain_regexp,
    )


def test_a_matching_path_is_recognised() -> None:
    assert _utils().check_request_path(make_message(path="/login"), "/login") is True


def test_a_different_path_is_not() -> None:
    assert _utils().check_request_path(make_message(path="/logout"), "/login") is False


def test_the_requests_path_is_read_percent_decoded() -> None:
    assert _utils().check_request_path(make_message(path="/caf%C3%A9"), "/café") is True


def test_a_relative_path_is_refused_as_a_route_name() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _utils().check_request_path(make_message(path="/login"), "login")


def test_an_empty_path_generates_itself() -> None:
    assert _utils().generate_uri("") == ""


def test_an_absolute_url_generates_itself() -> None:
    assert _utils().generate_uri("https://example.com/login") == "https://example.com/login"


def test_a_path_generates_through_the_builder() -> None:
    assert _utils().generate_uri("/login") == "/login"


def test_an_injected_builder_writes_the_uri() -> None:
    utils = _utils(uri_builder=_absolute_uri)

    assert utils.generate_uri("/login") == "https://example.com/login"


def _absolute_uri(path: str) -> str:
    """Return ``path`` under this test's one host, the way an app's builder would."""
    return f"https://example.com{path}"


def test_a_route_name_is_refused_on_generation() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _utils().generate_uri("login")


async def test_a_redirect_carries_the_location_and_the_status() -> None:
    response = _utils().create_redirect_response(make_message(), "/login")

    assert response.get_status_code() == 302
    assert response.get_header_line("location") == "/login"


async def test_a_redirect_may_carry_another_status() -> None:
    response = _utils().create_redirect_response(make_message(), "/login", status=303)

    assert response.get_status_code() == 303


async def test_a_domain_regexp_replaces_a_foreign_target() -> None:
    utils = _utils(domain_regexp=r"^https?://%s(/|$)")

    kept = utils.create_redirect_response(make_message(), "https://example.com/login")
    refused = utils.create_redirect_response(make_message(), "https://evil.example/login")

    assert kept.get_header_line("location") == "https://example.com/login"
    assert refused.get_header_line("location") == "/"


async def test_a_secure_domain_regexp_weighs_only_an_https_request() -> None:
    utils = _utils(secure_domain_regexp=r"^https?://%s(/|$)")

    refused = utils.create_redirect_response(make_message(), "https://evil.example/login")
    allowed = utils.create_redirect_response(make_message(host="other.example", path="/"), "/x")

    assert refused.get_header_line("location") == "/"
    assert allowed.get_header_line("location") == "/x"


async def test_the_host_is_named_with_its_port_when_not_the_default() -> None:
    utils = _utils(domain_regexp=r"^https?://example.com:8443(/|$)")
    proxied = make_message(host="example.com:8443", path="/")

    kept = utils.create_redirect_response(proxied, "https://example.com:8443/login")

    assert kept.get_header_line("location") == "https://example.com:8443/login"
