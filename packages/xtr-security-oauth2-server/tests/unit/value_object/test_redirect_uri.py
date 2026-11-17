"""A redirect URI is checked when it is made, so a stored one is always a URI."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from xtr_security_oauth2_server.value_object.redirect_uri import RedirectUri


@pytest.mark.parametrize(
    "uri",
    [
        "https://client.example.com/callback",
        "https://client.example.com",
        "http://127.0.0.1:8080/callback",
        "https://client.example.com/callback?next=1",
        "com.example.app:/oauth2redirect",
        "myapp:",
    ],
)
def test_it_accepts_a_uri(uri: str) -> None:
    assert str(RedirectUri(uri)) == uri


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "not a uri",
        "://client.example.com",
        "1https://client.example.com",
        "https://client example.com/callback",
        "/callback",
        "urn:ietf:wg:oauth:2.0:oob",
    ],
)
def test_it_refuses_what_is_not_a_uri(uri: str) -> None:
    with pytest.raises(InvalidArgumentError, match="not a valid URI"):
        _ = RedirectUri(uri)


@pytest.mark.parametrize(
    "uri",
    ["https://client.example.com/callback#done", "https://client.example.com/callback#"],
)
def test_a_fragment_is_refused(uri: str) -> None:
    # RFC 6749 §3.1.2: the endpoint URI must not include a fragment, because
    # the server puts what it answers there, and a registered one would be
    # overwritten or read by script on the client's page.
    with pytest.raises(InvalidArgumentError, match="fragment"):
        _ = RedirectUri(uri)


def test_two_uris_of_one_target_are_the_same_uri() -> None:
    assert RedirectUri("https://a.example.com/cb") == RedirectUri("https://a.example.com/cb")


def test_it_can_key_a_mapping() -> None:
    uri = RedirectUri("https://a.example.com/cb")

    assert {uri: 1}[RedirectUri("https://a.example.com/cb")] == 1
