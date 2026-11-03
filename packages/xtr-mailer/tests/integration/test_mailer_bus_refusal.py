"""A server's refusal, met by a bus handler in this process, raised with a finite chain."""

from __future__ import annotations

import anyio
import pytest
from rich.traceback import Traceback
from xtr_messenger import HandleMessageMiddleware, HandlersLocator, MessageBus
from xtr_mime import Email

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer import Mailer, TransportError
from xtr_mailer.messenger import SendEmailMessage
from xtr_mailer.transport.smtp import EsmtpTransport

pytestmark = pytest.mark.anyio


def _chain(error: BaseException) -> list[BaseException]:
    """Walk causes and contexts as a traceback renderer does; stop at an error seen twice."""
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None:
        assert all(current is not seen for seen in chain), "the error chain loops"
        chain.append(current)
        current = current.__cause__ or current.__context__
    return chain


async def _refused_through_the_bus() -> TransportError:
    async with ScriptedSmtpServer() as server:
        server.replies = {"MAIL": ["554 5.7.1 Sender rejected"]}
        transport = EsmtpTransport("localhost", server.port)

        async def send(message: SendEmailMessage) -> None:
            _ = await transport.send(message.message, message.envelope)

        handlers = HandlersLocator()
        _ = handlers.register(SendEmailMessage, send, name="send")
        bus = MessageBus([HandleMessageMiddleware(handlers)])
        email = Email().from_("sender@example.com").to("to@example.com").text("Hello")
        try:
            with pytest.raises(TransportError) as caught:
                await Mailer(transport, bus).send(email)
        finally:
            await transport.stop()
    return caught.value


async def test_the_servers_refusal_is_raised_as_the_transport_raised_it() -> None:
    error = await _refused_through_the_bus()

    assert "554" in str(error)
    assert not any(isinstance(link, TransportError) for link in _chain(error)[1:])


async def test_the_raised_error_renders_as_a_traceback() -> None:
    error = await _refused_through_the_bus()
    _ = _chain(error)

    with anyio.fail_after(5):
        rendered = await anyio.to_thread.run_sync(
            lambda: Traceback.from_exception(type(error), error, error.__traceback__),
            abandon_on_cancel=True,
        )

    assert rendered.trace.stacks
