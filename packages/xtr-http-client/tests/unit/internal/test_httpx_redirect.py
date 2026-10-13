from __future__ import annotations

import httpx
import pytest

from xtr_http_client.internal.httpx_redirect import next_hop, same_origin


def _answer(status: int, location: str | None = None) -> httpx.Response:
    headers = {} if location is None else {"Location": location}
    response = httpx.Response(
        status,
        headers=headers,
        request=httpx.Request("GET", "http://example.com/start"),
    )
    if location is not None:
        response.next_request = httpx.Request(
            "GET",
            httpx.URL("http://example.com/start").join(location),
        )

    return response


def test_an_answer_that_is_not_a_redirect_points_nowhere() -> None:
    assert next_hop(_answer(200)) is None


def test_an_absolute_location_is_where_the_next_hop_goes() -> None:
    following = next_hop(_answer(301, "http://elsewhere.test/moved"))

    assert following is not None
    assert str(following.url) == "http://elsewhere.test/moved"


def test_a_relative_location_is_resolved_against_the_url_it_arrived_on() -> None:
    following = next_hop(_answer(302, ".."))

    assert following is not None
    assert str(following.url) == "http://example.com/"


def test_a_location_naming_an_empty_authority_points_nowhere() -> None:
    assert next_hop(_answer(301, "//?foo=bar")) is None


def test_a_next_hop_with_no_host_points_nowhere() -> None:
    response = _answer(301, "http://example.com/moved")
    response.next_request = httpx.Request("GET", httpx.URL("/moved"))

    assert next_hop(response) is None


@pytest.mark.parametrize(
    ("other", "expected"),
    [
        ("http://example.com/elsewhere", True),
        ("http://example.com:80/elsewhere", True),
        ("https://example.com/elsewhere", False),
        ("http://example.org/elsewhere", False),
        ("http://example.com:8057/elsewhere", False),
    ],
)
def test_two_urls_are_one_origin_when_a_connection_would_be_the_same(
    other: str,
    expected: bool,
) -> None:
    one = httpx.URL("http://example.com/start")

    assert same_origin(one, httpx.URL(other)) is expected
