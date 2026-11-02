from __future__ import annotations

from xtr_messenger import Envelope, NonSendableStampInterface

from tests.support.messages import OrderPlaced
from tests.support.serializer import SERIALIZER
from xtr_orm_messenger.transport import OrmReceivedStamp


def test_it_never_leaves_the_process() -> None:
    envelope = Envelope(OrderPlaced("o-1"), (OrmReceivedStamp("7"),))

    sent = SERIALIZER.decode(SERIALIZER.encode(envelope))

    assert isinstance(OrmReceivedStamp("7"), NonSendableStampInterface)
    assert sent.last(OrmReceivedStamp) is None
