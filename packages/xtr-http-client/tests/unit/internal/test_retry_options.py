from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest

from xtr_http_client.internal.retry_options import (
    base_uri_rotation,
    replays_body,
    replays_request,
    retries,
    with_base_uri,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from xtr_http_message_contracts import RequestInterface


@final
class _Body:
    def __init__(self, size: int | None, seekable: bool) -> None:
        self._size = size
        self._seekable = seekable

    def get_size(self) -> int | None:
        return self._size

    def is_seekable(self) -> bool:
        return self._seekable


@final
class _Carrying:
    def __init__(self, body: _Body) -> None:
        self._body = body

    def get_body(self) -> _Body:
        return self._body


def _request(size: int | None, seekable: bool) -> RequestInterface:
    """A stand-in request whose body answers only what replaying asks about."""
    return cast("RequestInterface", cast("object", _Carrying(_Body(size, seekable))))


async def _produced() -> AsyncGenerator[bytes, None]:
    yield b"piece"


def test_one_base_uri_is_left_to_the_wrapped_client() -> None:
    assert base_uri_rotation("http://example.com/") is None
    assert base_uri_rotation(None) is None


def test_several_base_uris_are_read_as_the_order_to_move_along() -> None:
    assert base_uri_rotation(["http://a/", "http://b/"]) == ("http://a/", "http://b/")


def test_each_attempt_takes_the_next_base_uri() -> None:
    uris = ("http://a/", "http://b/")

    assert with_base_uri({}, uris, 0)["base_uri"] == "http://a/"
    assert with_base_uri({}, uris, 1)["base_uri"] == "http://b/"


def test_an_attempt_past_the_last_base_uri_stays_on_it() -> None:
    assert with_base_uri({}, ("http://a/", "http://b/"), 7)["base_uri"] == "http://b/"


def test_one_base_uri_is_passed_on_untouched() -> None:
    assert with_base_uri({"base_uri": "http://a/"}, (), 0) == {"base_uri": "http://a/"}


def test_a_list_of_base_uris_that_named_none_is_dropped() -> None:
    assert with_base_uri({"base_uri": []}, (), 0) == {}


def test_no_base_uri_at_all_stays_absent() -> None:
    assert with_base_uri({"timeout": 1.0}, (), 0) == {"timeout": 1.0}


def test_the_option_says_how_many_retries_a_request_may_have() -> None:
    assert retries(1, 3) == 1
    assert retries(0, 3) == 0


def test_a_request_saying_nothing_gets_what_the_client_was_built_with() -> None:
    truthy: object = True

    assert retries(None, 3) == 3
    assert retries(truthy, 3) == 3


def test_a_body_held_whole_can_be_sent_again() -> None:
    assert replays_body({"body": b"payload"}) is True
    assert replays_body({}) is True


@pytest.mark.anyio
async def test_a_body_produced_as_it_goes_cannot_be_sent_again() -> None:
    producing = _produced()
    try:
        assert replays_body({"body": producing}) is False
    finally:
        await producing.aclose()


def test_a_request_whose_body_rewinds_can_be_sent_again() -> None:
    assert replays_request(_request(7, seekable=True)) is True


def test_a_request_with_no_body_can_be_sent_again() -> None:
    assert replays_request(_request(0, seekable=False)) is True


def test_a_request_whose_body_was_read_to_its_end_cannot_be_sent_again() -> None:
    assert replays_request(_request(7, seekable=False)) is False
