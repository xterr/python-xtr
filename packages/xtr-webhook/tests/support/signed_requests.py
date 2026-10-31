"""Webhook bodies and signature entries built by hand, so a test does not trust the code under test.

The signature entries are made with ``hmac`` and ``base64`` directly, and a body is the JSON a
sender writes for an event, spelled out rather than produced by a serializer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

from xtr_http_message import ServerRequest

__all__ = ["EVENT_ID", "WHSEC", "arriving", "event_body", "legacy_entry", "standard_entry"]

WHSEC = "s3cr3t"
"""The secret both ends share. Named away from "secret" so the credential rule stays useful."""

EVENT_ID = "event-id"
"""The id every body and every entry here is for."""

_WHSEC_KEY = WHSEC.encode()


def event_body(
    name: str = "event-name",
    payload: dict[str, object] | None = None,
    tag: object = "remote_event",
) -> bytes:
    """Return the body a sender writes for a plain event: its tag, its fields, compact."""
    written = {"$type": tag, "name": name, "id": EVENT_ID, "payload": payload or {}}
    return json.dumps(written, separators=(",", ":")).encode()


def legacy_entry(event_name: str, body: bytes, key: str = WHSEC) -> str:
    """Return the legacy entry: the event's name, its id and the body, under ``key``."""
    digest = hmac.new(key.encode(), event_name.encode() + EVENT_ID.encode() + body, hashlib.sha256)
    return "sha256=" + digest.hexdigest()


def standard_entry(timestamp: int | str, body: bytes, key: bytes = _WHSEC_KEY) -> str:
    """Return the Standard Webhooks entry: the id, the timestamp and the body, under ``key``."""
    digest = hmac.new(key, f"{EVENT_ID}.{timestamp}.".encode() + body, hashlib.sha256)
    return "v1," + base64.b64encode(digest.digest()).decode()


def arriving(body: bytes, headers: dict[str, str] | None = None) -> ServerRequest:
    """Return a JSON ``POST`` carrying ``body``, with ``headers`` beside its media type."""
    return ServerRequest("POST", "/", {"Content-Type": "application/json", **(headers or {})}, body)
