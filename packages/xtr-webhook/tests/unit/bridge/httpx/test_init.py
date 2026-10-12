from __future__ import annotations

from xtr_webhook.bridge import httpx as httpx_bridge

_EXPORTED = [
    "HttpxSender",
    "NoPrivateNetworkTransport",
]


def test_every_exported_name_resolves() -> None:
    assert [name for name in httpx_bridge.__all__ if not hasattr(httpx_bridge, name)] == []


def test_it_exports_the_sender_and_the_guard() -> None:
    assert sorted(httpx_bridge.__all__) == _EXPORTED
