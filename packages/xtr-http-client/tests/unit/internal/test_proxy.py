from __future__ import annotations

from base64 import b64encode
from typing import TYPE_CHECKING

import pytest
from xtr_http_client_contracts import TransportError

from xtr_http_client.internal.proxy import get_proxy
from xtr_http_client.internal.url import parse_url

if TYPE_CHECKING:
    from xtr_http_client import UrlParts

_PROXY_VARIABLES = (
    "http_proxy",
    "HTTP_PROXY",
    "https_proxy",
    "HTTPS_PROXY",
    "all_proxy",
    "ALL_PROXY",
    "no_proxy",
    "NO_PROXY",
)


@pytest.fixture(autouse=True)
def _without_proxy_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _PROXY_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _url(url: str = "http://example.com/") -> UrlParts:
    return parse_url(url)


def test_no_proxy_anywhere_means_going_direct() -> None:
    assert get_proxy(None, _url(), None) is None


def test_the_proxy_the_caller_named_is_the_one_used() -> None:
    proxy = get_proxy("http://proxy.example.com:3128", _url(), None)

    assert proxy is not None
    assert proxy.url == "tcp://proxy.example.com:3128"
    assert proxy.auth is None
    assert proxy.no_proxy == ()


def test_a_proxy_written_as_host_and_port_is_reached_over_tcp() -> None:
    proxy = get_proxy("proxy.example.com:3128", _url(), None)

    assert proxy is not None
    assert proxy.url == "tcp://proxy.example.com:3128"


@pytest.mark.parametrize(
    ("proxy", "expected"),
    [
        ("http://proxy.example.com", "tcp://proxy.example.com:80"),
        ("https://proxy.example.com", "ssl://proxy.example.com:443"),
    ],
)
def test_a_proxy_that_names_no_port_gets_the_one_its_scheme_implies(
    proxy: str,
    expected: str,
) -> None:
    config = get_proxy(proxy, _url(), None)

    assert config is not None
    assert config.url == expected


def test_the_credentials_in_a_proxy_url_become_a_basic_authorization() -> None:
    proxy = get_proxy("http://u%40s:p%3Aw@proxy.example.com:3128", _url(), None)

    assert proxy is not None
    assert proxy.auth == "Basic " + b64encode(b"u@s:p:w").decode()


def test_a_proxy_user_with_no_password_still_authorizes() -> None:
    proxy = get_proxy("http://user@proxy.example.com:3128", _url(), None)

    assert proxy is not None
    assert proxy.auth == "Basic " + b64encode(b"user:").decode()


def test_the_environment_names_the_proxy_when_the_caller_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("http_proxy", "http://from-http-proxy:3128")

    proxy = get_proxy(None, _url(), None)

    assert proxy is not None
    assert proxy.url == "tcp://from-http-proxy:3128"


def test_the_uppercase_http_proxy_variable_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://from-uppercase:3128")

    assert get_proxy(None, _url(), None) is None


@pytest.mark.parametrize("name", ["all_proxy", "ALL_PROXY"])
def test_an_all_proxy_variable_covers_every_scheme(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setenv(name, "http://from-all-proxy:3128")

    proxy = get_proxy(None, _url(), None)

    assert proxy is not None
    assert proxy.url == "tcp://from-all-proxy:3128"


@pytest.mark.parametrize("name", ["https_proxy", "HTTPS_PROXY"])
def test_a_secure_request_prefers_the_https_proxy_variable(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    monkeypatch.setenv("http_proxy", "http://from-http-proxy:3128")
    monkeypatch.setenv(name, "http://from-https-proxy:3128")

    proxy = get_proxy(None, _url("https://example.com/"), None)

    assert proxy is not None
    assert proxy.url == "tcp://from-https-proxy:3128"


def test_the_hosts_to_reach_directly_are_split_on_commas_and_spaces() -> None:
    proxy = get_proxy("http://proxy:3128", _url(), "example.com, .internal\tlocalhost")

    assert proxy is not None
    assert proxy.no_proxy == ("example.com", ".internal", "localhost")


def test_the_environment_names_the_hosts_to_reach_directly_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_PROXY", "example.com")

    proxy = get_proxy("http://proxy:3128", _url(), None)

    assert proxy is not None
    assert proxy.no_proxy == ("example.com",)


def test_a_proxy_with_no_host_is_refused() -> None:
    with pytest.raises(TransportError) as raised:
        _ = get_proxy("http://", _url(), None)

    assert str(raised.value) == "Invalid HTTP proxy: host is missing."


def test_a_proxy_that_is_not_reached_over_http_is_refused() -> None:
    with pytest.raises(TransportError) as raised:
        _ = get_proxy("socks5://proxy:1080", _url(), None)

    assert str(raised.value) == 'Unsupported proxy scheme "socks5": "http" or "https" expected.'
