from __future__ import annotations

from xtr_notifier.transport import Dsn, NullTransport, TransportFactoryInterface


class _Structural:
    def create(self, dsn: Dsn) -> NullTransport:
        del dsn
        return NullTransport()

    def supports(self, dsn: Dsn) -> bool:
        return dsn.scheme == "structural"


def test_anything_that_creates_and_says_what_it_supports_is_a_factory() -> None:
    assert isinstance(_Structural(), TransportFactoryInterface)


def test_something_that_cannot_create_is_not_a_factory() -> None:
    assert not isinstance(object(), TransportFactoryInterface)
