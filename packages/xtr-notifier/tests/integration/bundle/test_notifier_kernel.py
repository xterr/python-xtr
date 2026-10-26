"""End-to-end: an application listing NotifierBundle notifies, chats and texts."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection import ContainerBuilder, Kernel, bundle_active
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_messenger import Envelope
from xtr_messenger.event import WorkerMessageFailedEvent

from tests.fixtures.app_notifier.config import ADMIN
from tests.fixtures.app_notifier.factories import SENT
from tests.fixtures.audit_bundle import AUDITED, AuditBundle
from xtr_notifier import (
    AdminRecipientsProviderInterface,
    ChatterInterface,
    NotifierInterface,
    TexterInterface,
)
from xtr_notifier.bundle import NotifierBundle
from xtr_notifier.bundle import notifier_bundle as bundle_module
from xtr_notifier.event_listener import NotificationLoggerListener
from xtr_notifier.exception import LogicError, UnsupportedSchemeError
from xtr_notifier.message import ChatMessage, PushMessage, SmsMessage
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.recipient import Recipient
from xtr_notifier.transport import Transport, Transports

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping

    from xtr_dependency_injection import BootedKernel
    from xtr_dependency_injection.bundle.bundle import AnyBundle

pytestmark = pytest.mark.anyio

APP = "tests.fixtures.app_notifier"
_ENVIRON = {"FAKE_CHAT_DSN": "fake://ops"}
_BUNDLES: Mapping[type[AnyBundle], Mapping[str, bool]] = {
    NotifierBundle: {"all": True},
    AuditBundle: {"all": True},
}


@pytest.fixture(autouse=True)
def _clear_recordings() -> None:
    SENT.clear()
    AUDITED.clear()


@pytest.fixture
async def booted() -> AsyncIterator[BootedKernel]:
    kernel = Kernel(APP, env="test", bundles=_BUNDLES, environ=_ENVIRON)
    async with await kernel.boot() as booted:
        yield booted


async def _notifier(booted: BootedKernel) -> NotifierInterface:
    return await booted.container.get(NotifierInterface)


async def test_a_notification_is_chatted_in_process_through_the_app_factory(
    booted: BootedKernel,
) -> None:
    await (await _notifier(booted)).send(Notification("Disk full", channels=["chat/fake"]))

    [(name, message)] = SENT
    assert name == "ops"
    assert isinstance(message, ChatMessage)
    assert message.subject == "Disk full"


async def test_a_discovered_provider_serves_its_scheme_beside_the_app_ones(
    booted: BootedKernel,
) -> None:
    await (await _notifier(booted)).send(Notification("Hello", channels=["chat/null"]))

    listener = await booted.container.get(NotificationLoggerListener)
    assert SENT == []
    assert [message.transport for message in listener.events.get_messages()] == ["null"]


async def test_a_failover_dsn_moves_to_the_next_provider(booted: BootedKernel) -> None:
    await (await _notifier(booted)).send(Notification("Hello", channels=["chat/failover"]))

    assert [name for name, _ in SENT] == ["backup"]


async def test_the_policy_picks_the_channels_of_a_notification_naming_none(
    booted: BootedKernel,
) -> None:
    recipient = Recipient(phone="+4912345678")

    await (await _notifier(booted)).send(
        Notification("Down", importance=Importance.URGENT), recipient
    )

    assert sorted((name, type(message).__name__) for name, message in SENT) == [
        ("ops", "ChatMessage"),
        ("texts", "SmsMessage"),
    ]


async def test_a_routed_message_is_queued_on_the_bus_and_sent_by_its_handler(
    booted: BootedKernel,
) -> None:
    texter = await booted.container.get(TexterInterface)

    sent = await texter.send(SmsMessage("+3312345678", "Your code"))
    _ = await texter.send(PushMessage("Shipped", "On its way"))

    listener = await booted.container.get(NotificationLoggerListener)
    assert sent is None
    assert [name for name, _ in SENT] == ["texts", "texts"]
    assert [event.queued for event in listener.events.get_events()] == [True, False, True, False]


async def test_a_push_notification_is_queued_and_sent_by_its_handler(
    booted: BootedKernel,
) -> None:
    await (await _notifier(booted)).send(Notification("Shipped", channels=["push/texts"]))

    [(name, message)] = SENT
    assert name == "texts"
    assert isinstance(message, PushMessage)


async def test_a_channel_tagged_by_another_bundle_joins_the_notifier(booted: BootedKernel) -> None:
    await (await _notifier(booted)).send(Notification("Logged in", channels=["audit"]))

    assert AUDITED == ["Logged in"]


async def test_a_factory_tagged_for_the_chatter_serves_the_chatter_alone(
    booted: BootedKernel,
) -> None:
    chat = await booted.container.get(Transport, "chatter")
    text = await booted.container.get(Transport, "texter")

    assert str(chat.from_string("chat-only://default")) == "null"
    with pytest.raises(UnsupportedSchemeError):
        _ = text.from_string("chat-only://default")


async def test_an_application_factory_serves_both_kinds(booted: BootedKernel) -> None:
    text = await booted.container.get(Transport, "texter")

    assert str(text.from_string("fake://other")) == "fake://other"


async def test_an_unrouted_message_is_sent_at_once(booted: BootedKernel) -> None:
    chatter = await booted.container.get(ChatterInterface)

    sent = await chatter.send(ChatMessage("Hello", transport="fake"))

    assert sent is not None
    assert sent.transport == "fake://ops"


async def test_the_transports_of_each_kind_are_named_after_the_configuration(
    booted: BootedKernel,
) -> None:
    chatter = await booted.container.get(Transports, "chatter")
    texter = await booted.container.get(Transports, "texter")

    assert str(chatter) == "[fake,failover,null]"
    assert str(texter) == "[texts]"


async def test_the_admin_recipients_are_the_configured_ones(booted: BootedKernel) -> None:
    provider = await booted.container.get(AdminRecipientsProviderInterface)

    [admin] = provider.admin_recipients
    assert isinstance(admin, Recipient)
    assert (admin.email, admin.phone) == (ADMIN.email, ADMIN.phone)


async def test_a_message_failed_for_good_is_reported_to_the_admins(booted: BootedKernel) -> None:
    dispatcher = await booted.container.get(EventDispatcherInterface)

    _ = await dispatcher.dispatch(
        WorkerMessageFailedEvent(Envelope(ChatMessage("x")), "async", RuntimeError("Boom"))
    )

    [(name, message)] = SENT
    assert name == "ops"
    assert message.subject == 'A "ChatMessage" message has just failed: RuntimeError: Boom.'


@pytest.mark.parametrize("missing", ["messenger", "event_dispatcher"])
def test_reporting_failed_messages_without_its_peers_fails_the_build(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    def active(builder: ContainerBuilder, name: str) -> bool:
        return name != missing and bundle_active(builder, name)

    monkeypatch.setattr(bundle_module, "bundle_active", active)
    kernel = Kernel(APP, env="test", bundles=_BUNDLES, environ=_ENVIRON)

    with pytest.raises(LogicError) as caught:
        _ = kernel.build()

    assert str(caught.value) == (
        f'"notification_on_failed_messages" needs the "{missing}" bundle; install '
        f"{'xtr-messenger' if missing == 'messenger' else 'xtr-event-dispatcher'} beside "
        "xtr-notifier, or turn the option off."
    )
