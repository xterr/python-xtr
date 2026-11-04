"""An S/MIME signer opens its certificate and key when built, and refuses what does not work.

No error names a key or a passphrase: each is checked through the whole chain of causes.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.support.smime_extra import require_smime_extra

require_smime_extra()

# Imported after the skip: without the extra these modules do not import.
from cryptography.hazmat.primitives import serialization  # noqa: E402 -- see above.
from cryptography.hazmat.primitives.asymmetric import ed25519  # noqa: E402 -- see above.

from tests.support.smime_certificates import (  # noqa: E402 -- see above.
    authority,
    recipient,
    signer_identity,
)
from tests.support.smime_checks import verifies, wire  # noqa: E402 -- see above.
from tests.support.smime_signing import message  # noqa: E402 -- see above.
from xtr_mime import InvalidArgumentError, LogicError, MimeRuntimeError  # noqa: E402 -- see above.
from xtr_mime.crypto import SMimeSigner  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from pathlib import Path

_SECRET = "c0rrect-h0rse"


def _chain(error: BaseException) -> list[BaseException]:
    errors: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in errors:
        errors.append(current)
        current = current.__cause__ or current.__context__
    return errors


def _assert_holds_no_secret(error: BaseException, *secrets: str) -> None:
    for item in _chain(error):
        for secret in secrets:
            assert secret not in str(item)
            assert secret not in repr(item)


@pytest.mark.parametrize("prefix", ["", "file://"])
def test_the_files_are_read_from_a_path_string(tmp_path: Path, prefix: str) -> None:
    certificate, key = signer_identity().write(tmp_path, "sign")

    signer = SMimeSigner(f"{prefix}{certificate}", f"{prefix}{key}")

    assert verifies(wire(signer.sign(message())), authority().certificate)


def test_a_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    certificate, _ = signer_identity().write(tmp_path, "sign")
    missing = tmp_path / "missing.key"

    with pytest.raises(MimeRuntimeError) as raised:
        _ = SMimeSigner(certificate, missing)

    assert str(raised.value) == f'File does not exist: "{missing}".'


def test_a_file_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    _, key = signer_identity().write(tmp_path, "sign")

    with pytest.raises(MimeRuntimeError) as raised:
        _ = SMimeSigner(tmp_path, key)

    assert str(raised.value).startswith(f'Unable to read the file "{tmp_path}": ')


def test_a_path_holding_a_null_byte_is_refused(tmp_path: Path) -> None:
    _, key = signer_identity().write(tmp_path, "sign")

    with pytest.raises(MimeRuntimeError) as raised:
        _ = SMimeSigner("a\x00b", key)

    assert str(raised.value).startswith('Unable to read the file "a\\x00b": ')


def test_a_certificate_that_does_not_load_is_refused(tmp_path: Path) -> None:
    _, key = signer_identity().write(tmp_path, "sign")
    garbage = tmp_path / "garbage.crt"
    _ = garbage.write_bytes(b"not a certificate")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(garbage, key)

    assert str(raised.value).startswith(f'Unable to load S/MIME certificate "{garbage}": ')


def test_a_key_that_does_not_load_is_refused_without_its_content(tmp_path: Path) -> None:
    certificate, _ = signer_identity().write(tmp_path, "sign")
    key = tmp_path / "broken.key"
    _ = key.write_bytes(
        b"-----BEGIN PRIVATE KEY-----\nc2VjcmV0LWtleQ==\n-----END PRIVATE KEY-----\n"
    )

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key)

    assert str(raised.value).startswith(f'Unable to load S/MIME private key "{key}": ')
    _assert_holds_no_secret(raised.value, "c2VjcmV0LWtleQ==")


@pytest.mark.parametrize("given", ["wr0ng-h0rse", ""])
def test_a_wrong_or_missing_passphrase_is_refused_without_it(tmp_path: Path, given: str) -> None:
    certificate, key = signer_identity().write(tmp_path, "sign", _SECRET)

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key, passphrase=given)

    assert str(raised.value).startswith(f'Unable to load S/MIME private key "{key}": ')
    _assert_holds_no_secret(raised.value, _SECRET, *([given] if given else []))


def test_a_passphrase_that_is_not_text_is_refused_without_it(tmp_path: Path) -> None:
    certificate, key = signer_identity().write(tmp_path, "sign", _SECRET)
    passphrase = "s3cret\ud800"

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key, passphrase=passphrase)

    assert str(raised.value) == (
        f'Unable to load S/MIME private key "{key}": the passphrase is not text that can be '
        "encoded."
    )
    _assert_holds_no_secret(raised.value, passphrase, "s3cret")


def test_a_passphrase_given_for_a_key_that_is_not_encrypted_is_refused(tmp_path: Path) -> None:
    certificate, key = signer_identity().write(tmp_path, "sign")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key, passphrase=_SECRET)

    assert str(raised.value).startswith(f'Unable to load S/MIME private key "{key}": ')
    _assert_holds_no_secret(raised.value, _SECRET)


def test_a_key_that_is_neither_rsa_nor_ec_is_refused(tmp_path: Path) -> None:
    certificate, _ = signer_identity().write(tmp_path, "sign")
    key = tmp_path / "ed25519.key"
    _ = key.write_bytes(
        ed25519.Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key)

    assert str(raised.value) == (
        f'Unable to load S/MIME private key "{key}": only an RSA or EC key signs S/MIME.'
    )


def test_a_key_that_does_not_match_the_certificate_is_refused(tmp_path: Path) -> None:
    certificate, _ = signer_identity().write(tmp_path, "sign")
    _, key = recipient().write(tmp_path, "other")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(certificate, key)

    assert str(raised.value) == (
        f'The S/MIME private key "{key}" does not match the certificate "{certificate}".'
    )


def test_an_unknown_algorithm_is_refused_before_any_file_is_read(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(InvalidArgumentError) as raised:
        _ = SMimeSigner(missing, missing, algorithm="md5")

    assert str(raised.value) == 'Invalid S/MIME signing algorithm "md5".'


def test_the_signer_shows_no_key_material(tmp_path: Path) -> None:
    certificate, key = signer_identity().write(tmp_path, "sign", _SECRET)

    signer = SMimeSigner(certificate, key, passphrase=_SECRET)

    assert _SECRET not in repr(signer)
    assert "PRIVATE KEY" not in repr(signer)
    assert not hasattr(signer, "__dict__")


def test_without_the_extra_building_a_signer_names_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "cryptography", None)
    monkeypatch.delitem(sys.modules, "xtr_mime.crypto._pkcs7", raising=False)

    with pytest.raises(LogicError) as raised:
        _ = SMimeSigner(tmp_path / "sign.crt", tmp_path / "sign.key")

    assert str(raised.value) == (
        'The "smime" extra is required to use S/MIME: uv add "xtr-mime[smime]".'
    )
