from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient

from tests.support.dummy_message import DummyMessage
from tests.support.recorded_events import recording_dispatcher
from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_notifier.message import MessageInterface, SentMessage
from xtr_notifier.transport import AbstractTransport

if TYPE_CHECKING:
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface


class _DummyTransport(AbstractTransport):
    def __init__(
        self,
        http_client: HttpClientInterface,
        event_dispatcher: EventDispatcherInterface | None = None,
        error: Exception | None = None,
    ) -> None:
        super().__init__(http_client, event_dispatcher)
        self.error: Exception | None = error

    @override
    def __str__(self) -> str:
        return f"dummy://{self._get_endpoint()}"

    @override
    def supports(self, message: MessageInterface) -> bool:
        return True

    def exposed_scheme(self) -> str:
        return self._get_http_scheme()

    @override
    async def _do_send(self, message: MessageInterface) -> SentMessage:
        if self.error is not None:
            raise self.error
        return SentMessage(message, str(self))


class _PlainHttpTransport(_DummyTransport):
    SSL: ClassVar[bool] = False


class _OwnHostTransport(_DummyTransport):
    HOST: ClassVar[str] = "api.example.test"


def test_the_scheme_is_https_by_default() -> None:
    assert _DummyTransport(MockHttpClient()).exposed_scheme() == "https"


def test_setting_ssl_switches_the_scheme() -> None:
    transport = _DummyTransport(MockHttpClient())

    assert transport.set_ssl(False).exposed_scheme() == "http"
    assert transport.set_ssl(True).exposed_scheme() == "https"


def test_unsetting_ssl_restores_the_transport_default() -> None:
    transport = _DummyTransport(MockHttpClient()).set_ssl(False)

    assert transport.set_ssl(None).exposed_scheme() == "https"


def test_a_transport_can_default_to_http() -> None:
    transport = _PlainHttpTransport(MockHttpClient())

    assert transport.exposed_scheme() == "http"
    assert transport.set_ssl(True).exposed_scheme() == "https"
    assert transport.set_ssl(None).exposed_scheme() == "http"


def test_the_endpoint_is_the_default_host_unless_overridden() -> None:
    assert str(_DummyTransport(MockHttpClient())) == "dummy://localhost"
    assert str(_OwnHostTransport(MockHttpClient())) == "dummy://api.example.test"


def test_the_endpoint_carries_a_host_and_a_port_set() -> None:
    transport = _DummyTransport(MockHttpClient()).set_host("example.test").set_port(8080)

    assert str(transport) == "dummy://example.test:8080"


def test_unsetting_the_host_and_port_restores_the_defaults() -> None:
    transport = _DummyTransport(MockHttpClient()).set_host("example.test").set_port(8080)

    assert str(transport.set_host(None).set_port(None)) == "dummy://localhost"


def test_it_keeps_the_http_client_for_subclasses() -> None:
    client = MockHttpClient()

    assert _DummyTransport(client)._http_client is client


@pytest.mark.anyio
async def test_it_sends_without_events_when_it_has_no_dispatcher() -> None:
    message = DummyMessage()

    sent = await _DummyTransport(MockHttpClient()).send(message)

    assert sent.original_message is message


@pytest.mark.anyio
async def test_it_announces_the_message_before_and_the_send_after() -> None:
    dispatcher, recorded = recording_dispatcher()
    message = DummyMessage()

    sent = await _DummyTransport(MockHttpClient(), dispatcher).send(message)

    assert [type(event) for event in recorded] == [MessageEvent, SentMessageEvent]
    first, second = recorded
    assert isinstance(first, MessageEvent)
    assert first.message is message
    assert not first.queued
    assert isinstance(second, SentMessageEvent)
    assert second.message is sent


@pytest.mark.anyio
async def test_a_failed_send_is_announced_then_raised() -> None:
    dispatcher, recorded = recording_dispatcher()
    error = RuntimeError("down")
    message = DummyMessage()
    transport = _DummyTransport(MockHttpClient(), dispatcher, error=error)

    with pytest.raises(RuntimeError) as caught:
        _ = await transport.send(message)

    assert caught.value is error
    assert [type(event) for event in recorded] == [MessageEvent, FailedMessageEvent]
    failed = recorded[1]
    assert isinstance(failed, FailedMessageEvent)
    assert failed.message is message
    assert failed.error is error
