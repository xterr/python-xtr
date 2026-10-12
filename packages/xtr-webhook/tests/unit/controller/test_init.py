from __future__ import annotations

from xtr_webhook import controller


def test_it_publishes_the_controller_the_endpoint_hands_a_webhook_to() -> None:
    assert sorted(controller.__all__) == ["WebhookController"]


def test_everything_it_publishes_is_there() -> None:
    assert all(hasattr(controller, name) for name in controller.__all__)
