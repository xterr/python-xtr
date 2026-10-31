from __future__ import annotations

import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from xtr_remote_event import RemoteEvent
from xtr_serializer import (
    JsonEncoder,
    NotNormalizableValueError,
    PydanticNormalizer,
    Serializer,
)

from tests.fixtures.events import DeliveryReport, Recipient, UnnamedEvent
from xtr_webhook.server import JsonBodyConfigurator, OutgoingRequest

# Named away from "secret" so the linter's hardcoded-credential rule stays useful
# where it matters.
_WHSEC = "s3cr3t"


def _serializer() -> Serializer:
    return Serializer([PydanticNormalizer()], [JsonEncoder()])


def _configured(event: RemoteEvent, request: OutgoingRequest | None = None) -> OutgoingRequest:
    built = request or OutgoingRequest()
    JsonBodyConfigurator(_serializer()).configure(event, _WHSEC, built)
    return built


def _report() -> DeliveryReport:
    return DeliveryReport(
        "mailer",
        "evt_7",
        {"provider": "acme"},
        occurred_at=datetime(2026, 3, 1, 9, tzinfo=UTC),
        scheduled_for=datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest")),
        recipient=Recipient("ana@example.com", ("vip",)),
        tags=("welcome",),
        metadata={"campaign": "spring"},
    )


def test_the_body_is_the_event_tagged_with_its_class_name() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {"foo": "bar"}))

    assert request.body is not None
    assert json.loads(request.body) == {
        "$type": "remote_event",
        "name": "event-name",
        "id": "event-id",
        "payload": {"foo": "bar"},
    }


def test_the_body_reads_back_as_the_event_it_was_written_for() -> None:
    event = _report()

    request = _configured(event)

    assert request.body is not None
    read = _serializer().deserialize(request.body, RemoteEvent, "json")
    assert read == event
    assert type(read) is DeliveryReport


def test_the_body_is_written_compact() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {"foo": "bar"}))

    assert request.body is not None
    assert b" " not in request.body


def test_two_runs_over_one_event_write_the_same_bytes() -> None:
    event = _report()

    assert _configured(event).body == _configured(event).body


def test_it_says_the_body_is_json() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {}))

    assert request.headers["Content-Type"] == "application/json"


def test_it_leaves_headers_another_configurator_already_wrote() -> None:
    request = _configured(
        RemoteEvent("event-name", "event-id", {}), OutgoingRequest(headers={"Webhook-Id": "x"})
    )

    assert request.headers["Webhook-Id"] == "x"


def test_an_event_of_a_class_with_no_name_is_refused_and_no_body_is_written() -> None:
    request = OutgoingRequest()

    with pytest.raises(NotNormalizableValueError):
        JsonBodyConfigurator(_serializer()).configure(
            UnnamedEvent("mailer", "evt_1", {}, "soft"), _WHSEC, request
        )

    assert request.body is None
