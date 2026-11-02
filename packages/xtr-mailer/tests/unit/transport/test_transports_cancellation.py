"""A send through :class:`Transports` cancelled mid-way leaves the email as it was."""

from __future__ import annotations

import asyncio

import anyio
import pytest
from xtr_mime import Headers, Message, TextPart

from tests.support.fake_transport import FakeTransport
from tests.support.stalling_transport import StallingTransport
from xtr_mailer.transport import Transports

pytestmark = pytest.mark.anyio


def _routed_email() -> Message:
    headers = Headers()
    _ = headers.add_text_header("X-Transport", "marketing")
    _ = headers.add_text_header("X-Transport", "main")
    _ = headers.add_mailbox_list_header("From", ["from@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    return Message(headers, TextPart("..."))


def _setup() -> tuple[FakeTransport, StallingTransport, Transports]:
    main, marketing = FakeTransport(), StallingTransport()
    return main, marketing, Transports({"main": main, "marketing": marketing})


async def test_an_asyncio_cancellation_puts_the_same_headers_back_in_order() -> None:
    _, _, transports = _setup()
    email = _routed_email()
    before = list(email.get_headers().all("X-Transport"))

    with pytest.raises(TimeoutError):
        _ = await asyncio.wait_for(transports.send(email), 0.05)

    after = list(email.get_headers().all("X-Transport"))
    assert [id(header) for header in after] == [id(header) for header in before]


async def test_an_anyio_cancel_scope_puts_the_same_headers_back_in_order() -> None:
    _, _, transports = _setup()
    email = _routed_email()
    before = list(email.get_headers().all("X-Transport"))

    with anyio.move_on_after(0.05):
        _ = await transports.send(email)

    after = list(email.get_headers().all("X-Transport"))
    assert [id(header) for header in after] == [id(header) for header in before]


async def test_a_retry_after_a_cancellation_reaches_the_named_transport() -> None:
    main, marketing, transports = _setup()
    email = _routed_email()
    with anyio.move_on_after(0.05):
        _ = await transports.send(email)

    sent = await transports.send(email)

    assert marketing.sent == [sent]
    assert main.sent == []
