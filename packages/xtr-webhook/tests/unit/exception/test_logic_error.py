from __future__ import annotations

from xtr_webhook.exception import LogicError, WebhookError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(LogicError, WebhookError)


def test_it_is_also_a_runtime_error() -> None:
    assert isinstance(LogicError("no configurator was given"), RuntimeError)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(LogicError("no configurator was given")) == "no configurator was given"
