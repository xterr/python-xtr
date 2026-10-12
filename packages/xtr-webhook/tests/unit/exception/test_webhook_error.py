from __future__ import annotations

from xtr_webhook.exception import WebhookError


def test_it_is_an_exception() -> None:
    assert issubclass(WebhookError, Exception)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(WebhookError("the receiver never answered")) == "the receiver never answered"
