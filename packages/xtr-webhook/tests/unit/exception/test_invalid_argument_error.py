from __future__ import annotations

from xtr_webhook.exception import InvalidArgumentError, WebhookError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(InvalidArgumentError, WebhookError)


def test_it_is_also_a_value_error() -> None:
    assert isinstance(InvalidArgumentError("a non-empty secret is required"), ValueError)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(InvalidArgumentError('"nope" is not a signature format')) == (
        '"nope" is not a signature format'
    )
