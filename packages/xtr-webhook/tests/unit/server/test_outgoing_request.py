from __future__ import annotations

from xtr_webhook.server import OutgoingRequest


def test_a_fresh_request_carries_no_headers_and_no_body() -> None:
    request = OutgoingRequest()

    assert request.headers == {}
    assert request.body is None


def test_each_request_gets_headers_of_its_own() -> None:
    first = OutgoingRequest()
    second = OutgoingRequest()

    first.headers["Webhook-Id"] = "event-id"

    assert second.headers == {}


def test_it_can_be_built_with_headers_and_a_body() -> None:
    request = OutgoingRequest(headers={"Webhook-Id": "event-id"}, body=b"{}")

    assert request.headers == {"Webhook-Id": "event-id"}
    assert request.body == b"{}"


def test_a_configurator_can_write_into_it() -> None:
    request = OutgoingRequest()

    request.headers["Content-Type"] = "application/json"
    request.body = b'{"foo":"bar"}'

    assert request.headers == {"Content-Type": "application/json"}
    assert request.body == b'{"foo":"bar"}'
