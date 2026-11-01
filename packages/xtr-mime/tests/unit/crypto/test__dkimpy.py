"""The dkim extra's two libraries: cryptography opens the key, dkimpy signs with it."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra these modules do not import.
from tests.support.dkim_keys import (  # noqa: E402 -- see above.
    DOMAIN,
    SELECTOR,
    dkim_key,
    ed25519_pem,
    short_rsa_pem,
)
from xtr_mime import InvalidArgumentError  # noqa: E402 -- see above.
from xtr_mime.crypto._dkimpy import (  # noqa: E402 -- see above.
    SignatureRequest,
    load_private_key,
    sign,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

_PREFIX = "Unable to load DKIM private key: "
_MESSAGE = b"From: a@testdkim.example.net\r\nTo: b@example.com\r\n\r\nBody\r\n"


def _key_lines(pem: str) -> list[str]:
    return [line for line in pem.splitlines() if not line.startswith("-----")]


@pytest.mark.parametrize("pem", [dkim_key().pem(), dkim_key().traditional_pem()])
def test_an_rsa_key_is_handed_on_as_traditional_pem(pem: str) -> None:
    assert load_private_key(pem.encode(), "") == dkim_key().traditional_pem().encode()


def test_a_key_is_decrypted_with_its_passphrase() -> None:
    loaded = load_private_key(dkim_key().pem("secret").encode(), "secret")

    assert loaded == dkim_key().traditional_pem().encode()


@pytest.mark.parametrize(
    ("pem", "passphrase"),
    [
        (dkim_key().pem("secret"), "wrong"),
        (dkim_key().pem("secret"), ""),
        (dkim_key().pem(), "secret"),
        ("not a key", ""),
    ],
    ids=["wrong passphrase", "no passphrase", "passphrase not needed", "not a key"],
)
def test_a_key_that_does_not_open_is_refused_without_its_content(pem: str, passphrase: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_private_key(pem.encode(), passphrase)

    assert str(raised.value).startswith(_PREFIX)
    assert not any(line in str(raised.value) for line in _key_lines(pem))
    assert "secret" not in str(raised.value)


def test_a_key_that_is_not_rsa_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_private_key(ed25519_pem().encode(), "")

    assert str(raised.value) == f'{_PREFIX}only an RSA key signs "rsa-sha256".'


def test_an_rsa_key_under_1024_bits_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_private_key(short_rsa_pem().encode(), "")

    assert str(raised.value) == (
        f"{_PREFIX}the RSA key has 512 bits; a DKIM verifier needs at least 1024."
    )


def test_a_passphrase_with_bytes_that_are_not_utf_8_opens_the_key() -> None:
    passphrase = os.fsdecode(b"p\xe4sswort-geheim")

    loaded = load_private_key(dkim_key().pem(passphrase).encode(), passphrase)

    assert loaded == dkim_key().traditional_pem().encode()


@pytest.mark.parametrize(
    "passphrase",
    [os.fsdecode(b"p\xe4sswort-geheim"), "geheim-\ud800-passwort"],
    ids=["wrong, not utf-8", "not encodable"],
)
def test_a_refused_passphrase_is_nowhere_in_the_error(passphrase: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = load_private_key(dkim_key().pem("secret").encode(), passphrase)

    assert str(raised.value).startswith(_PREFIX)
    assert not any("geheim" in shown for shown in _everything_shown(raised.value))


def _everything_shown(error: BaseException) -> Iterator[str]:
    """Yield what every error of the chain shows or holds: repr, str, args and attributes."""
    seen: BaseException | None = error
    while seen is not None:
        yield repr(seen)
        yield str(seen)
        yield repr(seen.args)
        yield repr(vars(seen))
        for name in ("object", "reason"):
            yield repr(getattr(seen, name, None))
        seen = seen.__cause__ or seen.__context__


def test_signing_returns_the_signature_field_dkimpy_folded() -> None:
    request = SignatureRequest(
        selector=SELECTOR,
        domain_name=DOMAIN,
        private_key=dkim_key().traditional_pem().encode(),
        canonicalization=("simple", "simple"),
        header_names=("From", "To"),
        show_body_length=True,
    )

    field = sign(_MESSAGE, request)

    assert field.startswith("DKIM-Signature: v=1; a=rsa-sha256; c=simple/simple;")
    assert "\r\n b=" in field
    assert " l=6;" in field
    assert dkim_key().verifies(field.encode() + _MESSAGE)
