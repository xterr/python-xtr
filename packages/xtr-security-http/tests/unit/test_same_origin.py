"""Telling a redirect target that leads back to the origin the request reached."""

from __future__ import annotations

import pytest
from xtr_http_message import ServerRequest

from tests.support.messages import make_message
from xtr_security_http._same_origin import is_same_origin


@pytest.mark.parametrize("target", ["/", "/after", "/after?page=2#top", "/%2F%2Fevil.example"])
def test_a_path_of_the_applications_own_is_on_the_same_origin(target: str) -> None:
    assert is_same_origin(make_message(), target) is True


def test_a_protocol_relative_target_is_on_another_host() -> None:
    assert is_same_origin(make_message(), "//evil.example/after") is False


@pytest.mark.parametrize(
    "target",
    [
        "/\\evil.example",
        "\\\\evil.example",
        "\\/evil.example",
        "https:\\\\evil.example",
        "https://evil.example\\@example.com/",
    ],
)
def test_a_target_carrying_a_backslash_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


@pytest.mark.parametrize(
    "target",
    ["/\t/evil.example", "/\n/evil.example", "/\r/evil.example", "/\x00/after", "/after\x7f"],
)
def test_a_target_carrying_a_control_character_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/after",
        "https://example.com",
        "HTTPS://EXAMPLE.COM/after",
        "https://example.com:443/after",
    ],
)
def test_an_absolute_url_with_the_requests_scheme_host_and_port_is_on_the_same_origin(
    target: str,
) -> None:
    assert is_same_origin(make_message(), target) is True


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/after",
        "https://example.com.evil.example/after",
        "https://example.com@evil.example/after",
        "https:evil.example",
        "https:///evil.example",
    ],
)
def test_an_absolute_url_on_another_host_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


@pytest.mark.parametrize(
    "target",
    ["http://example.com/after", "ftp://example.com/after", "javascript:alert(1)"],
)
def test_an_absolute_url_on_another_scheme_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


def test_an_absolute_url_on_another_port_is_refused() -> None:
    assert is_same_origin(make_message(), "https://example.com:8443/after") is False


def test_a_request_on_a_port_of_its_own_keeps_a_target_on_that_port() -> None:
    request = make_message(host="example.com:8443")

    assert is_same_origin(request, "https://example.com:8443/after") is True


def test_a_request_on_a_port_of_its_own_refuses_a_target_on_the_default_port() -> None:
    request = make_message(host="example.com:8443")

    assert is_same_origin(request, "https://example.com/after") is False


def test_an_ip_literal_host_is_matched_as_the_request_names_it() -> None:
    request = make_message(host="[::1]:8443")

    assert is_same_origin(request, "https://[::1]:8443/after") is True


@pytest.mark.parametrize("target", ["", "after", "?page=2", "#top"])
def test_a_relative_reference_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com:port/after",
        "https://example.com:99999/after",
        "https://[example.com/after",
    ],
)
def test_an_authority_no_parser_can_read_is_refused(target: str) -> None:
    assert is_same_origin(make_message(), target) is False


def test_a_request_naming_no_origin_has_no_absolute_url_on_its_origin() -> None:
    assert is_same_origin(ServerRequest("GET", "/"), "https://example.com/after") is False
