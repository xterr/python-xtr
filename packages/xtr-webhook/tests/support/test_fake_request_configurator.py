"""The fake configurator keeps the contract the transport is written against."""

from __future__ import annotations

from xtr_remote_event import RemoteEvent

from tests.support.fake_request_configurator import FakeRequestConfigurator
from xtr_webhook.server import OutgoingRequest, RequestConfiguratorInterface


def _event() -> RemoteEvent:
    return RemoteEvent(name="order.created", id="evt_1", payload={"total": 10})


def test_it_is_a_request_configurator() -> None:
    assert isinstance(FakeRequestConfigurator(), RequestConfiguratorInterface)


def test_it_records_every_call_in_order() -> None:
    configurator = FakeRequestConfigurator()
    first = OutgoingRequest()
    second = OutgoingRequest()

    configurator.configure(_event(), "first-secret", first)
    configurator.configure(_event(), "second-secret", second)

    assert [(secret, request) for _, secret, request in configurator.calls] == [
        ("first-secret", first),
        ("second-secret", second),
    ]


def test_it_records_the_request_it_was_handed_rather_than_a_copy() -> None:
    configurator = FakeRequestConfigurator()
    request = OutgoingRequest()

    configurator.configure(_event(), "s3cr3t", request)

    assert configurator.calls[0][2] is request


def test_it_applies_the_scripted_write() -> None:
    configurator = FakeRequestConfigurator(write=lambda request: setattr(request, "body", b"{}"))
    request = OutgoingRequest()

    configurator.configure(_event(), "s3cr3t", request)

    assert request.body == b"{}"


def test_without_a_write_it_leaves_the_request_alone() -> None:
    configurator = FakeRequestConfigurator()
    request = OutgoingRequest()

    configurator.configure(_event(), "s3cr3t", request)

    assert request == OutgoingRequest()
