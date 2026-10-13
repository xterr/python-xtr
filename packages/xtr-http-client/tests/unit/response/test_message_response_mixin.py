from __future__ import annotations

from typing import final

from xtr_http_message import Response, Stream

from xtr_http_client.response.message_response_mixin import MessageResponseMixin


@final
class Head(MessageResponseMixin):
    """The mixin alone, over a message."""

    __slots__ = ("extra",)

    def __init__(self, message: Response) -> None:
        super().__init__(message)
        self.extra: list[str] = []


def head() -> Head:
    return Head(Response(201, {"Content-Type": "application/json", "X-Id": ["1", "2"]}))


def test_it_answers_from_the_message() -> None:
    response = head()

    assert response.get_status_code() == 201
    assert response.get_reason_phrase() == "Created"
    assert response.get_protocol_version() == "1.1"
    assert response.get_headers() == {"Content-Type": ["application/json"], "X-Id": ["1", "2"]}


def test_header_names_are_matched_without_regard_to_case() -> None:
    response = head()

    assert response.has_header("content-type")
    assert response.get_header("x-id") == ["1", "2"]
    assert response.get_header_line("X-ID") == "1, 2"


def test_the_body_is_the_message_body() -> None:
    body = Stream.create(b"abc")

    assert Head(Response(200, body=body)).get_body() is body


def test_reading_the_status_code_counts_as_looking() -> None:
    response = head()

    _ = response.get_status_code()

    assert response._looked
    assert not response._first_pending


def test_reading_the_headers_counts_as_looking() -> None:
    response = head()

    _ = response.get_headers()

    assert response._looked


def test_reading_one_header_does_not_count_as_looking() -> None:
    response = head()

    _ = response.get_header_line("content-type")
    _ = response.has_header("x-id")

    assert not response._looked
    assert response._first_pending


def test_a_copy_carries_the_change_and_leaves_the_original_as_it_was() -> None:
    response = head()

    changed = response.with_header("X-Id", "3")

    assert changed is not response
    assert changed.get_header("x-id") == ["3"]
    assert response.get_header("x-id") == ["1", "2"]


def test_a_copy_shares_everything_but_the_message() -> None:
    response = head()

    changed = response.with_added_header("X-Id", "3")

    assert changed.extra is response.extra
    assert changed.get_header("x-id") == ["1", "2", "3"]


def test_every_kind_of_copy_carries_its_change() -> None:
    response = head()
    body = Stream.create(b"abc")

    assert response.with_protocol_version("2").get_protocol_version() == "2"
    assert not response.without_header("x-id").has_header("x-id")
    assert response.with_body(body).get_body() is body
    assert response.with_status(404).get_reason_phrase() == "Not Found"


def test_a_change_that_changes_nothing_hands_the_same_response_back() -> None:
    response = head()

    assert response.without_header("x-absent") is response
