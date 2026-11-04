from __future__ import annotations

import pytest
from xtr_mime import Email

from tests.support.recorded_events import recording_dispatcher
from xtr_mailer.event import MessageEvent, SentMessageEvent
from xtr_mailer.transport import NullTransport, RemoteTemplateTransportInterface


def test_it_is_named_null() -> None:
    assert str(NullTransport()) == "null://"


def test_it_sends_emails_rendered_from_a_remote_template() -> None:
    assert RemoteTemplateTransportInterface in type(NullTransport()).__mro__


@pytest.mark.anyio
async def test_it_sends_nowhere_but_reports_the_email_sent() -> None:
    dispatcher, recorded = recording_dispatcher()
    email = Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")

    sent = await NullTransport(dispatcher).send(email)

    assert sent is not None
    assert "Hello!" in sent.to_string()
    assert [type(event) for event in recorded] == [MessageEvent, SentMessageEvent]
