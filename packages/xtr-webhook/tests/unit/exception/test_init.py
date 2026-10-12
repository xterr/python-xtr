from __future__ import annotations

from xtr_webhook import exception
from xtr_webhook.exception import WebhookError

_EXPORTED: tuple[type[WebhookError], ...] = (
    exception.DeliveryError,
    exception.InvalidArgumentError,
    exception.LogicError,
    exception.PrivateNetworkError,
    exception.RejectWebhookError,
    exception.WebhookError,
    exception.WebhookRuntimeError,
)


def test_every_exported_name_resolves() -> None:
    assert [name for name in exception.__all__ if not hasattr(exception, name)] == []


def test_it_exports_every_error_this_library_raises() -> None:
    assert sorted(exception.__all__) == sorted(error.__name__ for error in _EXPORTED)


def test_every_error_it_exports_derives_from_the_base() -> None:
    assert [error for error in _EXPORTED if not issubclass(error, WebhookError)] == []
