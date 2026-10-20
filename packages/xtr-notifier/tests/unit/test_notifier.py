from __future__ import annotations

import pytest
from typing_extensions import override

from tests.support.channel_provider import ChannelProvider
from tests.support.fake_transport import FakeTransport
from tests.support.recording_channel import RecordingChannel
from xtr_notifier import AdminRecipientsProviderInterface, Notifier, NotifierInterface
from xtr_notifier.channel import ChannelPolicy, SmsChannel
from xtr_notifier.exception import InvalidArgumentError, LogicError
from xtr_notifier.notification import Importance, Notification
from xtr_notifier.recipient import NoRecipient, Recipient, RecipientInterface
from xtr_notifier.transport import NullTransport

pytestmark = pytest.mark.anyio


class _PerRecipient(Notification):
    @override
    def get_channels(self, recipient: RecipientInterface) -> tuple[str, ...]:
        return ("sms",) if isinstance(recipient, Recipient) else ("chat",)


async def test_it_refuses_an_sms_channel_without_a_recipient() -> None:
    notifier = Notifier({"sms": SmsChannel(NullTransport())})

    with pytest.raises(LogicError) as caught:
        await notifier.send(Notification("Hello World!", channels=["sms/twilio"]))

    assert str(caught.value) == 'The "sms" channel needs a Recipient.'


async def test_it_sends_to_nobody_in_particular_when_given_no_recipient() -> None:
    chat = RecordingChannel()
    notification = Notification("Hello", channels=["chat"])

    await Notifier({"chat": chat}).send(notification)

    assert len(chat.notified) == 1
    sent, recipient, transport_name = chat.notified[0]
    assert sent is notification
    assert isinstance(recipient, NoRecipient)
    assert transport_name is None


async def test_it_reads_the_transport_after_the_slash_of_a_channel() -> None:
    chat = RecordingChannel()

    await Notifier({"chat": chat}).send(Notification("Hello", channels=["chat/slack"]))

    assert chat.notified[0][2] == "slack"


async def test_it_sends_to_every_recipient_on_every_channel_it_names() -> None:
    chat, sms = RecordingChannel(), RecordingChannel()
    alice, bob = Recipient(phone="+1"), Recipient(phone="+2")

    await Notifier({"chat": chat, "sms": sms}).send(
        Notification("Hello", channels=["chat", "sms"]), alice, bob
    )

    assert [recipient for _, recipient, _ in chat.notified] == [alice, bob]
    assert [recipient for _, recipient, _ in sms.notified] == [alice, bob]


async def test_it_asks_the_notification_for_the_channels_of_each_recipient() -> None:
    chat, sms = RecordingChannel(), RecordingChannel()
    alice = Recipient(phone="+1")

    await Notifier({"chat": chat, "sms": sms}).send(_PerRecipient("Hello"), alice, NoRecipient())

    assert [recipient for _, recipient, _ in sms.notified] == [alice]
    assert len(chat.notified) == 1


async def test_it_asks_the_policy_when_the_notification_names_no_channel() -> None:
    chat = RecordingChannel()
    policy = ChannelPolicy({"urgent": ["chat/slack"]})

    await Notifier({"chat": chat}, policy).send(Notification("Down", importance=Importance.URGENT))

    assert chat.notified[0][2] == "slack"


async def test_it_refuses_a_notification_naming_no_channel_without_a_policy() -> None:
    with pytest.raises(LogicError) as caught:
        await Notifier({}).send(Notification("Hello"))

    assert str(caught.value) == (
        'Unable to determine which channels to use to send the "Notification" notification; '
        'you should either pass channels in the constructor, override its "get_channels()" '
        'method, or configure a "ChannelPolicy".'
    )


async def test_it_refuses_a_notification_the_policy_gives_no_channel() -> None:
    notifier = Notifier({}, ChannelPolicy({"high": []}))

    with pytest.raises(LogicError) as caught:
        await notifier.send(Notification("Hello"))

    assert str(caught.value) == (
        'Unable to determine which channels to use to send the "Notification" notification; '
        'the "ChannelPolicy" returns no channels for importance "high"; '
        'you should either pass channels in the constructor, override its "get_channels()" '
        "method."
    )


async def test_it_lets_the_policy_refuse_an_importance_it_does_not_define() -> None:
    with pytest.raises(InvalidArgumentError):
        await Notifier({}, ChannelPolicy({})).send(Notification("Hello"))


async def test_it_refuses_a_channel_that_does_not_exist() -> None:
    with pytest.raises(LogicError) as caught:
        await Notifier({}).send(Notification("Hello", channels=["chat"]))

    assert str(caught.value) == 'The "chat" channel does not exist.'


async def test_it_refuses_a_channel_that_does_not_support_the_recipient() -> None:
    with pytest.raises(LogicError) as caught:
        await Notifier({"push": RecordingChannel(supports=False)}).send(
            Notification("Hello", channels=["push"])
        )

    assert str(caught.value) == 'The "push" channel is not supported.'


async def test_it_sends_nothing_when_one_channel_of_a_recipient_is_refused() -> None:
    chat = RecordingChannel()

    with pytest.raises(LogicError):
        await Notifier({"chat": chat}).send(Notification("Hello", channels=["chat", "sms"]))

    assert chat.notified == []


async def test_it_builds_only_the_channels_it_uses_from_a_service_provider() -> None:
    chat = RecordingChannel()
    provider = ChannelProvider({"chat": chat, "sms": SmsChannel(FakeTransport())})

    await Notifier(provider).send(Notification("Hello", channels=["chat"]))

    assert provider.built == ["chat"]
    assert len(chat.notified) == 1


async def test_it_refuses_a_channel_a_service_provider_does_not_have() -> None:
    with pytest.raises(LogicError, match=r'^The "sms" channel does not exist\.$'):
        await Notifier(ChannelProvider({})).send(Notification("Hello", channels=["sms"]))


def test_it_provides_the_admin_recipients_it_was_given_and_added() -> None:
    first, second = Recipient("a@example.test"), Recipient("b@example.test")
    notifier = Notifier({}, admin_recipients=[first])

    notifier.add_admin_recipient(second)

    assert isinstance(notifier, NotifierInterface)
    assert isinstance(notifier, AdminRecipientsProviderInterface)
    assert notifier.admin_recipients == (first, second)
