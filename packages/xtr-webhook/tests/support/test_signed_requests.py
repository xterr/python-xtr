from __future__ import annotations

import base64
import hashlib
import hmac

import pytest
from xtr_remote_event import RemoteEvent
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer

from tests.support.signed_requests import (
    EVENT_ID,
    WHSEC,
    arriving,
    event_body,
    legacy_entry,
    standard_entry,
)


def test_an_event_body_reads_back_as_the_plain_event_it_spells_out() -> None:
    serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])

    read = serializer.deserialize(event_body("paid", {"total": 1}), RemoteEvent, "json")

    assert read == RemoteEvent("paid", EVENT_ID, {"total": 1})


def test_a_legacy_entry_covers_the_name_the_id_and_the_body() -> None:
    expected = hmac.new(WHSEC.encode(), b"paid" + EVENT_ID.encode() + b"{}", hashlib.sha256)

    assert legacy_entry("paid", b"{}") == "sha256=" + expected.hexdigest()


def test_a_standard_entry_covers_the_id_the_timestamp_and_the_body() -> None:
    digest = hmac.new(WHSEC.encode(), f"{EVENT_ID}.7.".encode() + b"{}", hashlib.sha256).digest()

    assert standard_entry(7, b"{}") == "v1," + base64.b64encode(digest).decode()


@pytest.mark.anyio
async def test_an_arriving_request_is_a_json_post_carrying_the_body() -> None:
    request = arriving(b"{}", {"Webhook-Id": EVENT_ID})

    assert request.get_method() == "POST"
    assert request.get_header_line("Content-Type") == "application/json"
    assert request.get_header_line("Webhook-Id") == EVENT_ID
    assert await request.get_body().get_contents() == b"{}"
