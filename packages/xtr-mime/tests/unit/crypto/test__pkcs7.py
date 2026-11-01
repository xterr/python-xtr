"""cryptography reads the certificates and keys, and signs and encrypts in canonical form."""

from __future__ import annotations

import pytest

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.short_rsa_key import short_rsa_pem  # noqa: E402 -- see above.
from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    authority,
    broken_key_certificate_pem,
    intermediate,
    recipient,
    rsa_pss_certificate_pem,
    signer_identity,
    unsupported_key_certificate_pem,
)
from tests.support.smime_checks import (  # noqa: E402 -- see above.
    decrypt,
    signed_parts,
    verifies,
)
from xtr_mime.crypto._pkcs7 import (  # noqa: E402 -- see above.
    Envelope,
    Signature,
    load_certificates,
    load_key_pair,
    load_recipient,
)
from xtr_mime.crypto._s_mime import PemFile  # noqa: E402 -- see above.
from xtr_mime.exception import InvalidArgumentError  # noqa: E402 -- see above.

# Lines ending in a bare line feed, which S/MIME signs and encrypts ending in CRLF.
_DATA = b"Content-Type: text/plain\n\nline one\nline two\n"
_CANONICAL = _DATA.replace(b"\n", b"\r\n")


def _signature() -> Signature:
    identity = signer_identity()
    certificate, key = load_key_pair(
        PemFile("sign.crt", identity.certificate_pem()), PemFile("sign.key", identity.key_pem()), ""
    )
    return Signature(certificate, key, (), "sha256")


def test_the_bytes_signed_are_the_canonical_form_of_those_given_and_verify() -> None:
    signed = _signature().sign(_DATA)

    assert signed_parts(signed)[0] == _CANONICAL
    assert verifies(signed, authority().certificate)


def test_the_bytes_encrypted_decrypt_to_the_canonical_form_of_those_given() -> None:
    encrypted = Envelope((recipient().certificate,), "aes-128-cbc").encrypt(_DATA)

    assert decrypt(encrypted, recipient()) == _CANONICAL


def test_a_signature_shows_no_key() -> None:
    assert "RSAPrivateKey" not in repr(_signature())


def test_every_certificate_of_a_file_is_read_in_order() -> None:
    pem = intermediate().certificate_pem() + authority().certificate_pem()

    certificates = load_certificates(PemFile("chain.pem", pem))

    assert certificates == [intermediate().certificate, authority().certificate]


def test_a_file_without_a_certificate_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_certificates(PemFile("empty.pem", b""))

    assert str(raised.value).startswith('Unable to load S/MIME certificate "empty.pem": ')


def test_a_bare_carriage_return_is_signed_as_the_crlf_it_is_written_as() -> None:
    signed = _signature().sign(b"X-C: a\rb\r\n\r\nbody\r\n")

    assert signed_parts(signed)[0] == b"X-C: a\r\nb\r\n\r\nbody\r\n"
    assert verifies(signed, authority().certificate)


_KEYS_THAT_DO_NOT_LOAD = pytest.mark.parametrize(
    "pem",
    [
        pytest.param(unsupported_key_certificate_pem(), id="an unsupported curve"),
        pytest.param(broken_key_certificate_pem(), id="a point off its curve"),
    ],
)


@_KEYS_THAT_DO_NOT_LOAD
def test_a_recipient_whose_key_does_not_load_is_refused(pem: bytes) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_recipient(PemFile("bad.crt", pem))

    assert str(raised.value).startswith('Unable to load the key of S/MIME certificate "bad.crt": ')


@_KEYS_THAT_DO_NOT_LOAD
def test_a_signer_whose_key_does_not_load_is_refused(pem: bytes) -> None:
    key = PemFile("sign.key", signer_identity().key_pem())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_key_pair(PemFile("bad.crt", pem), key, "")

    assert str(raised.value).startswith('Unable to load the key of S/MIME certificate "bad.crt": ')


def test_an_rsa_key_shorter_than_1024_bits_is_refused() -> None:
    certificate = PemFile("sign.crt", signer_identity().certificate_pem())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_key_pair(certificate, PemFile("short.key", short_rsa_pem()), "")

    assert str(raised.value) == (
        'Unable to load S/MIME private key "short.key": the RSA key has 512 bits; S/MIME needs '
        "at least 1024."
    )


def test_a_certificate_for_rsa_pss_is_refused_for_signing() -> None:
    key = PemFile("sign.key", signer_identity().key_pem())

    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_key_pair(PemFile("pss.crt", rsa_pss_certificate_pem()), key, "")

    assert str(raised.value) == (
        'The S/MIME certificate "pss.crt" holds an RSA-PSS key: a message is signed only with '
        "an RSA key for PKCS #1 v1.5 signatures, or an EC key."
    )
