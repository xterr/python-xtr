from __future__ import annotations

from xtr_webhook.exception import DeliveryError, WebhookError, WebhookRuntimeError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(DeliveryError, WebhookError)


def test_it_is_a_runtime_failure_a_bus_can_retry() -> None:
    error = DeliveryError(503, "https://example.test/hook")

    assert isinstance(error, WebhookRuntimeError)
    assert isinstance(error, RuntimeError)


def test_its_message_names_the_url_and_what_answered() -> None:
    assert str(DeliveryError(503, "https://example.test/hook")) == (
        'The webhook to "https://example.test/hook" was answered with HTTP 503.'
    )


def test_it_carries_the_status_code_and_the_url() -> None:
    error = DeliveryError(503, "https://example.test/hook")

    assert error.status_code == 503
    assert error.url == "https://example.test/hook"
