"""An application notifying on chat in-process and texting through its message bus."""

from __future__ import annotations

from xtr_dependency_injection import configure, env
from xtr_messenger import MessageBusConfig, TransportConfig

from xtr_notifier.bundle import AdminRecipientConfig, NotifierConfig
from xtr_notifier.message import PushMessage, SmsMessage

ADMIN = AdminRecipientConfig("admin@example.test", "+3312345678")


@configure
def notifier() -> NotifierConfig:
    """Chat through an env-configured provider, a failover pair and the null one; text one."""
    return NotifierConfig(
        chatter_transports={
            "fake": env("FAKE_CHAT_DSN"),
            "failover": "fake://down || fake://backup",
            "null": "null://null",
        },
        texter_transports={"texts": "fake://texts"},
        channel_policy={"urgent": ["chat/fake", "sms"], "high": ["chat/fake"]},
        admin_recipients=[ADMIN],
        notification_on_failed_messages=True,
    )


@configure
def messenger() -> MessageBusConfig:
    """Queue text and push messages on ``sync://``; chat messages stay unrouted."""
    return MessageBusConfig(
        transports={"sync": TransportConfig("sync://")},
        routing={SmsMessage: "sync", PushMessage: "sync"},
    )
