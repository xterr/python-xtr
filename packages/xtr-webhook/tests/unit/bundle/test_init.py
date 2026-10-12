from __future__ import annotations

from xtr_webhook import bundle

_EXPORTED = [
    "NoPrivateNetworkConfig",
    "RouteConfig",
    "WebhookBundle",
    "WebhookConfig",
]


def test_every_exported_name_resolves() -> None:
    assert [name for name in bundle.__all__ if not hasattr(bundle, name)] == []


def test_it_exports_the_bundle_and_its_configurations() -> None:
    assert sorted(bundle.__all__) == _EXPORTED
