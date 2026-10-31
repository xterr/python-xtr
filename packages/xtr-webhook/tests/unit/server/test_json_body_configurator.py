from __future__ import annotations

from datetime import datetime

import pytest
from xtr_remote_event import RemoteEvent
from xtr_serializer import JsonEncoder, NotNormalizableValueError, PydanticNormalizer, Serializer

from tests.fixtures.events import UnnamedEvent
from xtr_webhook.exception import InvalidArgumentError
from xtr_webhook.server import JsonBodyConfigurator, OutgoingRequest, SignatureFormat

# Named away from "secret" so the linter's hardcoded-credential rule stays useful
# where it matters.
_WHSEC = "s3cr3t"
_NOT_LEGACY = [SignatureFormat.STANDARD, SignatureFormat.TRANSITIONAL]
_NESTED: dict[str, object] = {
    "order": {"lines": [{"sku": "A-1", "qty": 2}], "note": None},
    "total": 42.5,
    "paid": True,
    "currency": "EUR",
}


def _configured(
    event: RemoteEvent,
    signature_format: SignatureFormat | str = SignatureFormat.LEGACY,
    request: OutgoingRequest | None = None,
) -> OutgoingRequest:
    built = request or OutgoingRequest()
    serializer = Serializer([PydanticNormalizer()], [JsonEncoder()])
    JsonBodyConfigurator(serializer, signature_format).configure(event, _WHSEC, built)
    return built


def test_the_legacy_body_is_exactly_the_serialized_payload() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", _NESTED))

    assert request.body == (
        b'{"order":{"lines":[{"sku":"A-1","qty":2}],"note":null},'
        b'"total":42.5,"paid":true,"currency":"EUR"}'
    )


@pytest.mark.parametrize("signature_format", _NOT_LEGACY)
def test_the_event_name_travels_in_the_payload_when_no_header_carries_it(
    signature_format: SignatureFormat,
) -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {"foo": "bar"}), signature_format)

    assert request.body == b'{"foo":"bar","type":"event-name"}'


@pytest.mark.parametrize("signature_format", _NOT_LEGACY)
def test_a_type_the_payload_already_carries_is_not_overwritten(
    signature_format: SignatureFormat,
) -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {"type": "set"}), signature_format)

    assert request.body == b'{"type":"set"}'


@pytest.mark.parametrize("signature_format", _NOT_LEGACY)
def test_the_events_payload_is_left_as_it_arrived(signature_format: SignatureFormat) -> None:
    payload: dict[str, object] = {"foo": "bar"}

    _ = _configured(RemoteEvent("event-name", "event-id", payload), signature_format)

    assert payload == {"foo": "bar"}


def test_only_the_payload_of_an_event_with_fields_of_its_own_is_written() -> None:
    request = _configured(UnnamedEvent("event-name", "event-id", {"foo": "bar"}, "soft"))

    assert request.body == b'{"foo":"bar"}'


def test_the_format_may_be_written_as_the_string_a_configuration_carries() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {}), "standard")

    assert request.body == b'{"type":"event-name"}'


def test_a_format_no_member_carries_is_refused_at_construction() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = JsonBodyConfigurator(Serializer([PydanticNormalizer()], [JsonEncoder()]), "nope")


def test_it_says_the_body_is_json() -> None:
    request = _configured(RemoteEvent("event-name", "event-id", {}))

    assert request.headers["Content-Type"] == "application/json"


def test_it_leaves_headers_another_configurator_already_wrote() -> None:
    request = _configured(
        RemoteEvent("event-name", "event-id", {}),
        request=OutgoingRequest(headers={"Webhook-Id": "x"}),
    )

    assert request.headers["Webhook-Id"] == "x"


@pytest.mark.parametrize(
    "value",
    [datetime(2026, 3, 1, 9, 30), {"a", "b"}],  # noqa: DTZ001 — the naive datetime is the case.
    ids=["naive-datetime", "set"],
)
def test_a_payload_value_json_cannot_carry_is_refused_and_no_body_is_written(
    value: object,
) -> None:
    request = OutgoingRequest()

    with pytest.raises(NotNormalizableValueError) as refused:
        _ = _configured(RemoteEvent("event-name", "event-id", {"when": value}), request=request)

    assert request.body is None
    assert "2026" not in str(refused.value)
    assert "'a'" not in str(refused.value)
