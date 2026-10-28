"""The IsCsrfTokenValid marker: metadata, method filter, and value extraction."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

import pytest
from fastapi.params import Depends as DependsParam
from starlette.requests import Request

from xtr_security_http.decorator.is_csrf_token_valid import (
    SOURCE_HEADER,
    SOURCE_PAYLOAD,
    SOURCE_QUERY,
    IsCsrfTokenValid,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(IsCsrfTokenValid("delete_book"), DependsParam)


def test_it_records_the_metadata_shape() -> None:
    marker = IsCsrfTokenValid("delete_book", token_key="csrf", methods=["POST", "get"])  # noqa: S106

    assert marker.token_id == "delete_book"  # noqa: S105
    assert marker.token_key == "csrf"  # noqa: S105
    assert marker.methods == ("POST", "GET", "HEAD")
    assert marker.token_source == SOURCE_PAYLOAD


def test_the_default_token_key_is_the_form_one() -> None:
    assert IsCsrfTokenValid("delete_book").token_key == "_token"  # noqa: S105


def test_the_sources_are_the_bitmask() -> None:
    assert SOURCE_PAYLOAD == 0b0001
    assert SOURCE_QUERY == 0b0010
    assert SOURCE_HEADER == 0b0100


def test_the_dependency_reads_the_request_and_delegates_to_the_checker() -> None:
    dependency = IsCsrfTokenValid("delete_book").dependency
    assert dependency is not None

    parameters = inspect.signature(dependency).parameters

    assert "request" in parameters
    assert "checker" in parameters


def _request(
    *,
    method: str = "POST",
    query: bytes = b"",
    headers: list[tuple[bytes, bytes]] | None = None,
    body: bytes = b"",
) -> Request:
    """Build a starlette request over a hand-rolled scope and receive channel."""
    messages: list[dict[str, object]] = [
        {"type": "http.request", "body": body, "more_body": False},
        {"type": "http.disconnect"},
    ]

    async def receive() -> dict[str, object]:
        return messages.pop(0) if messages else {"type": "http.disconnect"}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/",
            "query_string": query,
            "headers": headers or [],
        },
        receive=receive,
    )


@final
class RecordingChecker:
    """Stands in for the injected checker, recording what the dependency handed it."""

    def __init__(self) -> None:
        self.checked: list[tuple[str, str | None]] = []

    async def check(self, is_csrf_token_valid: IsCsrfTokenValid, token_value: str | None) -> None:
        """Record the pair instead of deciding; the pair is what the tests read."""
        self.checked.append((is_csrf_token_valid.token_id, token_value))


async def _checked(marker: IsCsrfTokenValid, request: Request) -> tuple[str, str | None]:
    """Run the marker's dependency over ``request`` and a recording checker."""
    checker = RecordingChecker()
    assert marker.dependency is not None
    dependency = cast("Callable[..., Awaitable[None]]", marker.dependency)
    await dependency(request, checker)
    return checker.checked[0]


async def test_it_reads_the_value_from_the_json_payload() -> None:
    request = _request(
        headers=[(b"content-type", b"application/json")],
        body=b'{"_token": "from-json"}',
    )

    assert await _checked(IsCsrfTokenValid("delete_book"), request) == (
        "delete_book",
        "from-json",
    )


async def test_it_reads_the_value_from_the_form_payload() -> None:
    request = _request(
        headers=[(b"content-type", b"application/x-www-form-urlencoded")],
        body=b"_token=from-form",
    )

    assert await _checked(IsCsrfTokenValid("delete_book"), request) == (
        "delete_book",
        "from-form",
    )


async def test_it_reads_the_value_from_the_query_when_the_bitmask_names_it() -> None:
    request = _request(query=b"_token=from-query")

    marker = IsCsrfTokenValid("delete_book", token_source=SOURCE_QUERY)

    assert await _checked(marker, request) == ("delete_book", "from-query")


async def test_it_reads_the_value_from_the_header_when_the_bitmask_names_it() -> None:
    request = _request(headers=[(b"x-csrf-token", b"from-header")])

    marker = IsCsrfTokenValid(
        "delete_book",
        token_key="x-csrf-token",  # noqa: S106
        token_source=SOURCE_HEADER,
    )

    assert await _checked(marker, request) == ("delete_book", "from-header")


async def test_the_first_named_source_with_a_value_wins() -> None:
    request = _request(
        query=b"x-csrf-token=from-query",
        headers=[(b"x-csrf-token", b"from-header")],
    )

    marker = IsCsrfTokenValid(
        "delete_book",
        token_key="x-csrf-token",  # noqa: S106
        token_source=SOURCE_QUERY | SOURCE_HEADER,
    )

    assert await _checked(marker, request) == ("delete_book", "from-query")


async def test_a_source_the_bitmask_leaves_out_is_never_read() -> None:
    request = _request(query=b"_token=from-query")

    marker = IsCsrfTokenValid("delete_book", token_source=SOURCE_PAYLOAD)

    assert await _checked(marker, request) == ("delete_book", None)


async def test_a_method_the_marker_leaves_out_skips_the_check() -> None:
    checker = RecordingChecker()
    marker = IsCsrfTokenValid("delete_book", methods=["POST"])
    assert marker.dependency is not None
    dependency = cast("Callable[..., Awaitable[None]]", marker.dependency)

    await dependency(_request(method="GET", query=b"_token=x"), checker)

    assert checker.checked == []


async def test_a_named_method_runs_the_check() -> None:
    checker = RecordingChecker()
    marker = IsCsrfTokenValid("delete_book", methods=["POST"], token_source=SOURCE_QUERY)
    assert marker.dependency is not None
    dependency = cast("Callable[..., Awaitable[None]]", marker.dependency)

    await dependency(_request(method="POST", query=b"_token=x"), checker)

    assert checker.checked == [("delete_book", "x")]
