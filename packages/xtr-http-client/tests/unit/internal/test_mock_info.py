from __future__ import annotations

from xtr_http_message import Response

from xtr_http_client.internal.mock_info import issued_info

URL = "https://example.com/orders"


def test_the_record_is_of_the_request_that_was_made() -> None:
    info = issued_info({}, Response(201), "POST", URL, {"user_data": "seven"})

    assert info["http_method"] == "POST"
    assert info["url"] == URL
    assert info["http_code"] == 201
    assert info["user_data"] == "seven"
    assert info["canceled"] is False
    assert info["error"] is None
    assert info["response_headers"] == ["HTTP/1.1 201 Created"]


def test_nothing_was_followed_so_nothing_was_counted() -> None:
    info = issued_info({}, Response(), "GET", URL, {})

    assert info["redirect_count"] == 0
    assert info["redirect_url"] is None


def test_the_time_the_transfer_took_is_measured_when_the_script_does_not_say() -> None:
    info = issued_info({}, Response(), "GET", URL, {})
    total_time = info["total_time"]

    assert isinstance(total_time, float)
    assert total_time > 0.0


def test_a_reading_the_script_gives_is_the_reading_the_record_carries() -> None:
    info = issued_info(
        {"start_time": 1701187598.313123, "total_time": 4.2},
        Response(),
        "GET",
        URL,
        {},
    )

    assert info["start_time"] == 1701187598.313123
    assert info["total_time"] == 4.2


def test_a_reading_that_is_not_one_is_not_taken_for_one() -> None:
    info = issued_info({"start_time": True, "total_time": "4.2"}, Response(), "GET", URL, {})
    start_time = info["start_time"]
    total_time = info["total_time"]

    assert isinstance(start_time, float)
    assert start_time > 1.0
    assert isinstance(total_time, float)


def test_an_entry_the_script_added_is_carried_through() -> None:
    info = issued_info({"primary_ip": "127.0.0.1"}, Response(), "GET", URL, {})

    assert info["primary_ip"] == "127.0.0.1"
