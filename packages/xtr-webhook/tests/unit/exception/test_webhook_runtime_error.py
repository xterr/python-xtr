from __future__ import annotations

from xtr_webhook.exception import WebhookError, WebhookRuntimeError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(WebhookRuntimeError, WebhookError)


def test_it_is_also_a_runtime_error() -> None:
    assert isinstance(WebhookRuntimeError("the receiver refused it"), RuntimeError)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(WebhookRuntimeError("the receiver refused it")) == "the receiver refused it"
