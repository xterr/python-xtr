from __future__ import annotations

from typing import cast

import pytest

from tests.support.fake_backend import URL, FakeBackend, FakeBackends

pytestmark = pytest.mark.anyio


def test_the_response_carries_the_head_it_was_given() -> None:
    response = FakeBackend(404, {"Content-Type": "text/plain"}).response

    assert response.get_status_code() == 404
    assert response.get_reason_phrase() == "Not Found"
    assert response.get_header_line("content-type") == "text/plain"


def test_the_info_has_every_entry_a_response_always_reports() -> None:
    info = cast("dict[str, object]", FakeBackend().response.get_info())

    assert set(info) == {
        "canceled",
        "error",
        "http_code",
        "http_method",
        "redirect_count",
        "redirect_url",
        "response_headers",
        "start_time",
        "url",
        "user_data",
    }
    assert info["url"] == URL


def test_the_raw_head_opens_with_the_status_line() -> None:
    backend = FakeBackend(400, {"Content-Type": "application/json"})

    assert backend.info["response_headers"] == [
        "HTTP/1.1 400 Bad Request",
        "Content-Type: application/json",
    ]


def test_pieces_are_pushed_where_the_previous_one_ended() -> None:
    backend = FakeBackend()

    backend.send(b"abc", b"de")
    backend.finish()

    chunks = [backend.transfer.take_ready() for _ in range(3)]
    assert [(chunk.get_offset(), chunk.is_last()) for chunk in chunks if chunk] == [
        (0, False),
        (3, False),
        (5, True),
    ]


async def test_an_answer_is_the_whole_body(backends: FakeBackends) -> None:
    response = backends.make().answer(b"abc", b"def")

    assert await response.get_content() == b"abcdef"


async def test_cancelling_the_response_stops_the_producer() -> None:
    backend = FakeBackend()

    await backend.response.cancel()

    assert backend.stopped


def test_a_fed_transfer_waits_as_long_as_it_was_told() -> None:
    assert FakeBackend(timeout=0.5).transfer.timeout == 0.5


async def test_closing_them_all_closes_every_body_made() -> None:
    made = FakeBackends()
    backend = made.make(buffered=False)

    await made.close()

    assert not backend.response.get_body().is_readable()
