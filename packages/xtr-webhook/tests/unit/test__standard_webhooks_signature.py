from __future__ import annotations

import base64
import hashlib
import hmac

from xtr_webhook._standard_webhooks_signature import PREFIX, sign

# Reproduced from the Standard Webhooks reference (https://www.standardwebhooks.com/);
# every value below is part of the published vector. Nothing here is a guess to be
# "corrected": a change to any of them means this package no longer interoperates.
_VECTOR_ID = "msg_p5jXN8AQM9LWM0D4loKWxJek"
_VECTOR_TIMESTAMP = "1614265330"
_VECTOR_BODY = b'{"test": 2432232314}'
_VECTOR_WHSEC = "whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw"
_VECTOR_SIGNATURE = "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="


def _expected(message: bytes, key: bytes) -> str:
    return PREFIX + base64.b64encode(hmac.new(key, message, hashlib.sha256).digest()).decode()


def test_it_reproduces_the_standard_webhooks_reference_vector() -> None:
    """The vector is reproduced from the Standard Webhooks reference, not computed here.

    It is the one check that this package signs what every other implementation of the
    scheme signs, so a mismatch is a bug in the signing, never in the vector.
    """
    assert sign(_VECTOR_ID, _VECTOR_TIMESTAMP, _VECTOR_BODY, _VECTOR_WHSEC) == _VECTOR_SIGNATURE


def test_the_prefix_is_the_scheme_version() -> None:
    assert PREFIX == "v1,"


def test_a_signature_starts_with_the_prefix() -> None:
    assert sign(_VECTOR_ID, _VECTOR_TIMESTAMP, _VECTOR_BODY, _VECTOR_WHSEC).startswith(PREFIX)


def test_it_signs_the_id_the_timestamp_and_the_body_in_that_order() -> None:
    key = base64.b64decode("MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw", validate=True)
    expected = _expected(b"msg_1.1700000000." + b'{"amount": 10}', key)

    signature = sign("msg_1", "1700000000", b'{"amount": 10}', _VECTOR_WHSEC)

    assert signature == expected


def test_a_prefixed_secret_is_the_base64_it_carries() -> None:
    key = base64.b64decode("MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw", validate=True)

    assert sign("msg_1", "1", b"{}", _VECTOR_WHSEC) == _expected(b"msg_1.1.{}", key)


def test_an_unprefixed_secret_is_the_key_as_it_stands() -> None:
    assert sign("msg_1", "1", b"{}", "plain-shared-value") == _expected(
        b"msg_1.1.{}", b"plain-shared-value"
    )


def test_a_prefixed_secret_that_is_not_base64_is_the_key_as_it_stands() -> None:
    whsec = "whsec_not base64!!"

    assert sign("msg_1", "1", b"{}", whsec) == _expected(b"msg_1.1.{}", whsec.encode())


def test_a_bare_prefix_falls_back_to_the_secret_as_the_key() -> None:
    assert sign("id", "1", b"{}", "whsec_") == _expected(b"id.1.{}", b"whsec_")


def test_a_tampered_body_does_not_keep_the_signature() -> None:
    signed = sign("msg_1", "1700000000", b'{"amount": 10}', _VECTOR_WHSEC)
    tampered = sign("msg_1", "1700000000", b'{"amount": 99}', _VECTOR_WHSEC)

    assert signed != tampered


def test_another_timestamp_does_not_keep_the_signature() -> None:
    signed = sign("msg_1", "1700000000", b"{}", _VECTOR_WHSEC)
    replayed = sign("msg_1", "1800000000", b"{}", _VECTOR_WHSEC)

    assert signed != replayed


def test_another_id_does_not_keep_the_signature() -> None:
    signed = sign("msg_1", "1700000000", b"{}", _VECTOR_WHSEC)
    other = sign("msg_2", "1700000000", b"{}", _VECTOR_WHSEC)

    assert signed != other


def test_another_secret_does_not_keep_the_signature() -> None:
    signed = sign("msg_1", "1700000000", b"{}", _VECTOR_WHSEC)
    other = sign("msg_1", "1700000000", b"{}", "whsec_TWZLUTlyOEdLWXFyVHdqVVBEOElM")

    assert signed != other
