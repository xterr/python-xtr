"""The fake sender keeps the contract the transport is written against."""

from __future__ import annotations

import pytest

from tests.support.fake_http_sender import FakeHttpSender
from xtr_webhook.server import HttpSenderInterface

pytestmark = pytest.mark.anyio


def test_it_is_an_http_sender() -> None:
    assert isinstance(FakeHttpSender(), HttpSenderInterface)


async def test_it_answers_the_status_it_was_built_with() -> None:
    sender = FakeHttpSender(status_code=503)

    assert await sender.post("https://receiver.test/hook", {}, b"{}") == 503


async def test_it_answers_the_same_status_however_often_it_is_called() -> None:
    sender = FakeHttpSender()

    first = await sender.post("https://receiver.test/hook", {}, b"{}")
    second = await sender.post("https://receiver.test/hook", {}, b"{}")

    assert (first, second) == (200, 200)


async def test_it_records_every_post_in_order() -> None:
    sender = FakeHttpSender()

    _ = await sender.post("https://first.test/hook", {"Webhook-Id": "evt_1"}, b"first")
    _ = await sender.post("https://second.test/hook", {"Webhook-Id": "evt_2"}, b"second")

    assert sender.posts == [
        ("https://first.test/hook", {"Webhook-Id": "evt_1"}, b"first"),
        ("https://second.test/hook", {"Webhook-Id": "evt_2"}, b"second"),
    ]


async def test_it_records_the_headers_it_was_handed_rather_than_a_copy() -> None:
    sender = FakeHttpSender()
    headers = {"Webhook-Id": "evt_1"}

    _ = await sender.post("https://receiver.test/hook", headers, b"{}")

    assert sender.posts[0][1] is headers
