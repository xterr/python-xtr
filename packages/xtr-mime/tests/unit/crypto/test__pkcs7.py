"""cryptography reads the certificates and keys, and signs and encrypts in canonical form."""

from __future__ import annotations

import pytest

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    authority,
    intermediate,
    recipient,
    signer_identity,
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
