from __future__ import annotations

from tests.support.fake_transport import FakeTransport
from tests.support.scripted_transport import ScriptedTransport
from xtr_mailer.transport import StoppableTransportInterface


class _Connection(ScriptedTransport):
    async def stop(self) -> None:
        pass


def test_a_transport_that_can_stop_is_stoppable() -> None:
    assert isinstance(_Connection("smtp://a"), StoppableTransportInterface)


def test_a_transport_without_a_session_to_stop_is_not_stoppable() -> None:
    assert not isinstance(FakeTransport(), StoppableTransportInterface)


def test_something_that_only_stops_is_not_a_stoppable_transport() -> None:
    class _Stops:
        async def stop(self) -> None:
            pass

    assert not isinstance(_Stops(), StoppableTransportInterface)
