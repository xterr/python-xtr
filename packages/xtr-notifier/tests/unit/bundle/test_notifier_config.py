from __future__ import annotations

import pytest

from xtr_notifier.bundle import AdminRecipientConfig, NotifierConfig
from xtr_notifier.exception import InvalidArgumentError


def test_it_is_built_bare_with_nothing_configured() -> None:
    config = NotifierConfig()

    assert dict(config.chatter_transports) == {}
    assert dict(config.texter_transports) == {}
    assert dict(config.channel_policy) == {}
    assert tuple(config.admin_recipients) == ()
    assert config.notification_on_failed_messages is False
    assert config.http_client is None


def test_it_accepts_a_policy_keyed_by_importance() -> None:
    config = NotifierConfig(channel_policy={"urgent": ["sms", "chat/slack"], "low": []})

    assert dict(config.channel_policy) == {"urgent": ["sms", "chat/slack"], "low": []}


def test_it_refuses_a_policy_key_that_is_no_importance() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = NotifierConfig(channel_policy={"loud": ["chat"]})

    assert str(caught.value) == (
        'The channel policy names "loud", which is no importance; '
        'use one of "urgent", "high", "medium", "low".'
    )


def test_it_keeps_the_admin_recipients() -> None:
    admin = AdminRecipientConfig("admin@example.test", "+3312345678")

    assert tuple(NotifierConfig(admin_recipients=[admin]).admin_recipients) == (admin,)
