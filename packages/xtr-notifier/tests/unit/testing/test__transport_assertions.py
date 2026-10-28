from __future__ import annotations

from typing import ClassVar

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient

from xtr_notifier.exception import UnsupportedMessageTypeError
from xtr_notifier.message import ChatMessage, MessageInterface, SentMessage, SmsMessage
from xtr_notifier.testing import TransportCases, assert_transport_cases
from xtr_notifier.transport import AbstractTransport

pytestmark = pytest.mark.anyio


class _ChatTransport(AbstractTransport):
    HOST: ClassVar[str] = "chat.example.test"

    @override
    def __str__(self) -> str:
        return f"chat://{self._get_endpoint()}?channel=ops"

    @override
    def supports(self, message: MessageInterface) -> bool:
        return isinstance(message, ChatMessage)

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        if not isinstance(message, ChatMessage):
            raise UnsupportedMessageTypeError(str(self), "ChatMessage", message)
        return SentMessage(message, str(self))


class _CarelessTransport(_ChatTransport):
    """Sends what it says it does not support, and hides its endpoint."""

    @override
    def __str__(self) -> str:
        return "careless://"

    @override
    def supports(self, message: MessageInterface) -> bool:
        return isinstance(message, SmsMessage)

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        if isinstance(message, SmsMessage):
            raise ConnectionError("down")
        return SentMessage(message, str(self))


def _chat() -> _ChatTransport:
    return _ChatTransport(MockHttpClient())


def _careless() -> _CarelessTransport:
    return _CarelessTransport(MockHttpClient())


async def test_it_passes_a_transport_that_does_what_its_cases_say() -> None:
    await assert_transport_cases(
        TransportCases(
            create_transport=_chat,
            to_string=[("chat://chat.example.test?channel=ops", _chat())],
            supported=[ChatMessage("Hello")],
            unsupported=[SmsMessage("+33", "Hello")],
        )
    )


async def test_it_reports_every_case_a_transport_fails_at_once() -> None:
    cases = TransportCases(
        create_transport=_careless,
        to_string=[("careless://default", _careless())],
        supported=[ChatMessage("Hello")],
        unsupported=[SmsMessage("+33", "Hi"), ChatMessage("Hey")],
    )

    with pytest.raises(AssertionError) as caught:
        await assert_transport_cases(cases)

    assert str(caught.value).splitlines() == [
        "The transport fails 8 case(s):",
        '- it reads "careless://", not "careless://default"',
        (
            "- it does not support ChatMessage(subject='Hello', options=None, transport=None, "
            "notification=None)"
        ),
        (
            "- it supports SmsMessage(phone='+33', subject='Hi', from_='', options=None, "
            "transport=None, notification=None)"
        ),
        (
            "- sending SmsMessage(phone='+33', subject='Hi', from_='', options=None, "
            "transport=None, notification=None) raised ConnectionError: down, "
            "not UnsupportedMessageTypeError"
        ),
        (
            "- sending ChatMessage(subject='Hey', options=None, transport=None, notification=None) "
            "raised nothing, not UnsupportedMessageTypeError"
        ),
        '- it reads "careless://" with the host set to "host.test"',
        '- it reads "careless://" with the port set to 42',
        '- it reads "careless://" with the host set to "host.test" and the port to 42',
    ]
