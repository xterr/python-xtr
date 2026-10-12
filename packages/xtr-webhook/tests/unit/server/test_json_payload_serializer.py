from __future__ import annotations

import json

import pytest

from xtr_webhook.server import JsonPayloadSerializer


def test_it_returns_bytes_so_the_signature_covers_what_is_sent() -> None:
    assert JsonPayloadSerializer().serialize({"foo": "bar"}) == b'{"foo":"bar"}'


def test_it_keeps_the_payload_order_so_two_runs_sign_the_same_bytes() -> None:
    payload: dict[str, object] = {"b": 1, "a": 2}

    assert JsonPayloadSerializer().serialize(payload) == b'{"b":1,"a":2}'


def test_an_empty_payload_is_an_empty_object() -> None:
    assert JsonPayloadSerializer().serialize({}) == b"{}"


def test_it_writes_nested_values_as_json() -> None:
    payload: dict[str, object] = {"items": [1, 2], "nested": {"on": True}, "none": None}

    assert json.loads(JsonPayloadSerializer().serialize(payload)) == payload


def test_a_payload_it_cannot_write_is_refused() -> None:
    with pytest.raises(TypeError):
        _ = JsonPayloadSerializer().serialize({"what": object()})
