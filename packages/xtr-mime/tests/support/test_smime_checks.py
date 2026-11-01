"""The S/MIME checks accept what cryptography signs and refuse what does not hold.

The signer tests trust :func:`verifies`; here it is checked against signatures cryptography
makes on its own, unchanged and changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402 -- see above.
from cryptography.hazmat.primitives.serialization import pkcs7  # noqa: E402 -- see above.

from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    Identity,
    authority,
    chained_signer,
    ec_signer,
    intermediate,
    recipient,
    signer_identity,
)
from tests.support.smime_checks import (  # noqa: E402 -- see above.
    decrypt,
    openssl_verifies,
    signed_parts,
    verifies,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_CONTENT = b"Content-Type: text/plain\r\n\r\nsigned\r\n"


def _signed(identity: Identity, *extra: Identity) -> bytes:
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(_CONTENT)
        .add_signer(identity.certificate, identity.private_key, hashes.SHA256())
    )
    for certificate in extra:
        builder = builder.add_certificate(certificate.certificate)
    return builder.sign(
        serialization.Encoding.SMIME,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )


@pytest.mark.parametrize("identity", [signer_identity, ec_signer])
def test_a_signature_cryptography_makes_verifies(identity: Callable[[], Identity]) -> None:
    assert verifies(_signed(identity()), authority().certificate)


def test_the_signed_part_is_cut_as_sent() -> None:
    assert signed_parts(_signed(signer_identity()))[0] == _CONTENT


def test_a_changed_signed_part_does_not_verify() -> None:
    sent = _signed(signer_identity()).replace(b"signed\r\n", b"signed!\r\n", 1)

    assert not verifies(sent, authority().certificate)


def test_a_signer_the_trusted_ca_did_not_issue_does_not_verify() -> None:
    assert not verifies(_signed(signer_identity()), recipient().certificate)


def test_a_chain_verifies_only_with_its_intermediate() -> None:
    assert verifies(_signed(chained_signer(), intermediate()), authority().certificate)
    assert not verifies(_signed(chained_signer()), authority().certificate)


def test_a_message_that_is_not_signed_does_not_verify() -> None:
    assert not verifies(b"Content-Type: text/plain\r\n\r\nhi\r\n", authority().certificate)


def test_openssl_agrees_where_it_is_installed(tmp_path: Path) -> None:
    good = openssl_verifies(_signed(signer_identity()), authority().certificate, tmp_path)
    if good is None:
        pytest.skip("no openssl binary installed")
    sent = _signed(signer_identity()).replace(b"signed\r\n", b"signed!\r\n", 1)

    assert good
    assert openssl_verifies(sent, authority().certificate, tmp_path) is False


def test_an_encrypted_message_decrypts_to_its_content() -> None:
    encrypted = (
        pkcs7.PKCS7EnvelopeBuilder()
        .set_data(_CONTENT)
        .add_recipient(recipient().certificate)
        .encrypt(serialization.Encoding.SMIME, [pkcs7.PKCS7Options.Binary])
    )

    assert decrypt(encrypted, recipient()) == _CONTENT
