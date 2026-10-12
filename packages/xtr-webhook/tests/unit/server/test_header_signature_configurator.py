from __future__ import annotations

import base64
import hashlib
import hmac

import pytest
from xtr_remote_event import RemoteEvent

from xtr_webhook.exception import InvalidArgumentError, LogicError
from xtr_webhook.server import HeaderSignatureConfigurator, OutgoingRequest, SignatureFormat

_BODY = b'{"foo":"bar"}'
# Named away from "secret" so the linter's hardcoded-credential rule stays useful
# where it matters.
_WHSEC = "s3cr3t"
_TIMESTAMP = "1700000000"
_MISSING_TIMESTAMP = (
    'The "Webhook-Timestamp" header must be set when emitting a Standard Webhooks '
    'signature; ensure "HeadersConfigurator" runs before this configurator.'
)
_NOT_LEGACY = [SignatureFormat.STANDARD, SignatureFormat.TRANSITIONAL]


def _event() -> RemoteEvent:
    return RemoteEvent("event-name", "event-id", {})


def _legacy(key: bytes = b"s3cr3t", algorithm: str = "sha256") -> str:
    digest = hmac.new(key, b"event-name" + b"event-id" + _BODY, algorithm).hexdigest()

    return f"{algorithm}={digest}"


def _standard(key: bytes = b"s3cr3t") -> str:
    digest = hmac.new(key, b"event-id." + _TIMESTAMP.encode() + b"." + _BODY, hashlib.sha256)

    return "v1," + base64.b64encode(digest.digest()).decode()


def _signed() -> OutgoingRequest:
    return OutgoingRequest(headers={"Webhook-Timestamp": _TIMESTAMP}, body=_BODY)


def test_the_legacy_format_is_the_default() -> None:
    request = OutgoingRequest(body=_BODY)

    HeaderSignatureConfigurator().configure(_event(), _WHSEC, request)

    assert request.headers["Webhook-Signature"] == _legacy()


def test_the_legacy_signature_covers_the_name_then_the_id_then_the_body() -> None:
    request = OutgoingRequest(body=_BODY)
    swapped = hmac.new(b"s3cr3t", b"event-id" + b"event-name" + _BODY, "sha256").hexdigest()

    HeaderSignatureConfigurator().configure(_event(), _WHSEC, request)

    assert request.headers["Webhook-Signature"] != f"sha256={swapped}"


def test_the_standard_format_signs_the_id_the_timestamp_and_the_body() -> None:
    request = _signed()

    HeaderSignatureConfigurator(signature_format=SignatureFormat.STANDARD).configure(
        _event(),
        _WHSEC,
        request,
    )

    assert request.headers["Webhook-Signature"] == _standard()


def test_the_standard_format_uses_the_decoded_prefixed_secret() -> None:
    request = _signed()
    prefixed = "whsec_" + base64.b64encode(b"raw-key-bytes").decode()

    HeaderSignatureConfigurator(signature_format=SignatureFormat.STANDARD).configure(
        _event(),
        prefixed,
        request,
    )

    assert request.headers["Webhook-Signature"] == _standard(b"raw-key-bytes")


def test_the_transitional_format_emits_both_signatures_space_separated() -> None:
    request = _signed()

    HeaderSignatureConfigurator(signature_format=SignatureFormat.TRANSITIONAL).configure(
        _event(),
        _WHSEC,
        request,
    )

    assert request.headers["Webhook-Signature"].split(" ") == [_legacy(), _standard()]


@pytest.mark.parametrize("signature_format", _NOT_LEGACY)
def test_it_refuses_to_sign_without_the_timestamp_header(
    signature_format: SignatureFormat,
) -> None:
    request = OutgoingRequest(body=_BODY)

    with pytest.raises(LogicError) as refused:
        HeaderSignatureConfigurator(signature_format=signature_format).configure(
            _event(),
            _WHSEC,
            request,
        )

    assert str(refused.value) == _MISSING_TIMESTAMP


def test_the_missing_timestamp_header_is_named_as_it_was_configured() -> None:
    request = OutgoingRequest(body=_BODY)

    with pytest.raises(LogicError) as refused:
        HeaderSignatureConfigurator(
            signature_format=SignatureFormat.STANDARD,
            timestamp_header_name="X-Timestamp",
        ).configure(_event(), _WHSEC, request)

    assert str(refused.value) == _MISSING_TIMESTAMP.replace("Webhook-Timestamp", "X-Timestamp")


def test_the_timestamp_header_name_is_configurable() -> None:
    request = OutgoingRequest(headers={"X-Timestamp": _TIMESTAMP}, body=_BODY)

    HeaderSignatureConfigurator(
        signature_format=SignatureFormat.STANDARD,
        timestamp_header_name="X-Timestamp",
    ).configure(_event(), _WHSEC, request)

    assert request.headers["Webhook-Signature"] == _standard()


def test_the_signature_header_name_is_configurable() -> None:
    request = OutgoingRequest(body=_BODY)

    HeaderSignatureConfigurator(signature_header_name="X-Signature").configure(
        _event(),
        _WHSEC,
        request,
    )

    assert request.headers["X-Signature"] == _legacy()


def test_another_algorithm_signs_and_names_itself() -> None:
    request = OutgoingRequest(body=_BODY)

    HeaderSignatureConfigurator(algorithm="sha512").configure(_event(), _WHSEC, request)

    assert request.headers["Webhook-Signature"] == _legacy(algorithm="sha512")


def test_an_algorithm_this_runtime_cannot_make_is_refused_at_construction() -> None:
    with pytest.raises(InvalidArgumentError) as refused:
        _ = HeaderSignatureConfigurator(algorithm="sha0")

    assert str(refused.value) == 'The signing algorithm "sha0" is not available.'


def test_an_empty_secret_is_refused() -> None:
    request = OutgoingRequest(body=_BODY)

    with pytest.raises(InvalidArgumentError) as refused:
        HeaderSignatureConfigurator().configure(_event(), "", request)

    assert str(refused.value) == "A non-empty secret is required."


@pytest.mark.parametrize("signature_format", [*_NOT_LEGACY, SignatureFormat.LEGACY])
def test_a_request_with_no_body_cannot_be_signed(signature_format: SignatureFormat) -> None:
    request = OutgoingRequest(headers={"Webhook-Timestamp": _TIMESTAMP})

    with pytest.raises(LogicError) as refused:
        HeaderSignatureConfigurator(signature_format=signature_format).configure(
            _event(),
            _WHSEC,
            request,
        )

    assert str(refused.value) == "The body must be set."


def test_an_empty_body_is_a_body_and_is_signed() -> None:
    request = OutgoingRequest(body=b"")

    HeaderSignatureConfigurator().configure(_event(), _WHSEC, request)

    digest = hmac.new(b"s3cr3t", b"event-name" + b"event-id", "sha256").hexdigest()
    assert request.headers["Webhook-Signature"] == f"sha256={digest}"


def test_it_leaves_headers_another_configurator_already_wrote() -> None:
    request = _signed()

    HeaderSignatureConfigurator(signature_format=SignatureFormat.STANDARD).configure(
        _event(),
        _WHSEC,
        request,
    )

    assert request.headers["Webhook-Timestamp"] == _TIMESTAMP


def test_it_leaves_the_body_alone() -> None:
    request = _signed()

    HeaderSignatureConfigurator(signature_format=SignatureFormat.TRANSITIONAL).configure(
        _event(),
        _WHSEC,
        request,
    )

    assert request.body == _BODY


def test_the_format_may_be_written_as_the_string_a_configuration_carries() -> None:
    request = _signed()

    HeaderSignatureConfigurator(signature_format="standard").configure(_event(), _WHSEC, request)

    assert request.headers["Webhook-Signature"] == _standard()


def test_a_format_no_member_carries_is_refused_at_construction() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = HeaderSignatureConfigurator(signature_format="nope")
