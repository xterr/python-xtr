"""What the request mixin promises beyond any one request class.

The method, the request-target and the URI are exercised through the classes
that carry them; what is here is the mixin's own promise about the ``Host``
header — where it comes from, when it is left alone, and what case it keeps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import pytest

from xtr_http_message.request import Request
from xtr_http_message.server_request import ServerRequest
from xtr_http_message.uri import Uri

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_message_contracts import RequestInterface


class _Build(Protocol):
    """How both request classes are built, as far as these tests need."""

    def __call__(
        self,
        method: str,
        uri: str,
        headers: Mapping[str, str | Sequence[str]] | None = None,
    ) -> RequestInterface: ...


_REQUESTS = [
    pytest.param(Request, id="request"),
    pytest.param(ServerRequest, id="server_request"),
]


@pytest.mark.parametrize("build", _REQUESTS)
def test_a_uri_with_no_host_gives_the_request_no_host_header(build: _Build) -> None:
    assert build("GET", "/").has_header("Host") is False


@pytest.mark.parametrize("build", _REQUESTS)
def test_a_new_uri_with_no_host_leaves_the_host_header_as_it_was(build: _Build) -> None:
    request = build("GET", "http://foo.com/bar")

    assert request.with_uri(Uri("/baz")).get_header_line("Host") == "foo.com"


@pytest.mark.parametrize("build", _REQUESTS)
def test_preserving_the_host_of_a_request_that_has_none_takes_it_from_the_uri(
    build: _Build,
) -> None:
    request = build("GET", "/")

    replaced = request.with_uri(Uri("http://foo.com/bar"), preserve_host=True)

    assert replaced.get_header_line("Host") == "foo.com"


@pytest.mark.parametrize("build", _REQUESTS)
def test_the_host_header_keeps_the_case_it_was_given_in_when_the_uri_changes(
    build: _Build,
) -> None:
    request = build("GET", "http://foo.com/bar", {"hOsT": "foo.com"})

    replaced = request.with_uri(Uri("http://baz.com/bar"))

    assert replaced.get_headers() == {"hOsT": ["baz.com"]}


@pytest.mark.parametrize("build", _REQUESTS)
def test_the_host_header_moves_to_the_front_when_the_uri_changes(build: _Build) -> None:
    request = build("GET", "/", {"Foo": "Bar", "Host": "a.com"})

    replaced = request.with_uri(Uri("http://baz.com/bar"))

    assert list(replaced.get_headers()) == ["Host", "Foo"]


@pytest.mark.parametrize("build", _REQUESTS)
def test_a_request_target_set_by_hand_survives_a_new_uri(build: _Build) -> None:
    request = build("GET", "http://foo.com/bar").with_request_target("*")

    assert request.with_uri(Uri("http://baz.com/qux?a=b")).get_request_target() == "*"


@pytest.mark.parametrize("build", _REQUESTS)
def test_a_method_is_kept_exactly_as_given(build: _Build) -> None:
    assert build("GET", "/").with_method("pAtCh").get_method() == "pAtCh"


@pytest.mark.parametrize("build", _REQUESTS)
def test_setting_a_method_leaves_the_request_it_was_asked_of_alone(build: _Build) -> None:
    request = build("GET", "/")

    _ = request.with_method("POST")

    assert request.get_method() == "GET"
