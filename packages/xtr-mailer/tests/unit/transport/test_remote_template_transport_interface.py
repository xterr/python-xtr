from __future__ import annotations

from tests.support.fake_transport import FakeTransport
from xtr_mailer.transport import NullTransport, RemoteTemplateTransportInterface


def test_a_transport_declares_it_by_deriving_from_it() -> None:
    assert RemoteTemplateTransportInterface in type(NullTransport()).__mro__


def test_a_transport_that_does_not_derive_from_it_does_not_have_it() -> None:
    assert RemoteTemplateTransportInterface not in type(FakeTransport()).__mro__
