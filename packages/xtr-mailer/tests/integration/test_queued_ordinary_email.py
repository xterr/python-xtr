"""An ordinary email, in any script and to many people, is queued and sent — never refused."""

from __future__ import annotations

import anyio
import pytest

from tests.support.ordinary_emails import ORDINARY
from tests.support.queue import through_the_queue
from xtr_mailer.messenger import MessageHandler
from xtr_mailer.transport import NullTransport


@pytest.mark.parametrize("name", list(ORDINARY), ids=str)
def test_an_ordinary_email_is_queued_and_sent(name: str) -> None:
    received = anyio.run(through_the_queue, ORDINARY[name]())

    sent = anyio.run(MessageHandler(NullTransport()), received)

    assert sent is not None
