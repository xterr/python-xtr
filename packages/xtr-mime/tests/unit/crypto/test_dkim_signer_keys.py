"""The key a DKIM signer signs with, the domain and selector it names, and the extra it needs."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest

from tests.support.dkim_extra import require_dkim_extra

require_dkim_extra()

# Imported after the skip: without the extra the key helper does not import.
from tests.support.dkim_keys import DOMAIN, SELECTOR, dkim_key  # noqa: E402 -- see above.
from tests.support.dkim_signing import signer, wire  # noqa: E402 -- see above.
from xtr_mime import Email, InvalidArgumentError, LogicError  # noqa: E402 -- see above.
from xtr_mime.crypto import DkimSigner  # noqa: E402 -- see above.

if TYPE_CHECKING:
    from pathlib import Path


def _email() -> Email:
    return Email().from_(f"fabien@{DOMAIN}").to("b@example.com").subject("Hi").text("Body")


@pytest.mark.parametrize("prefix", ["", "file://"])
def test_the_key_is_read_from_a_file(tmp_path: Path, prefix: str) -> None:
    path = tmp_path / "dkim.pem"
    _ = path.write_text(dkim_key().pem())
    private_key = f"{prefix}{path}" if prefix else path

    signed = DkimSigner(private_key, DOMAIN, SELECTOR).sign(_email())

    assert dkim_key().verifies(wire(signed))


def test_a_key_file_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "missing.pem"

    with pytest.raises(InvalidArgumentError) as raised:
        _ = DkimSigner(path, DOMAIN, SELECTOR)

    assert str(raised.value) == (
        f'Unable to load DKIM private key: the file "{path}" cannot be read: '
        "No such file or directory."
    )


@pytest.mark.parametrize("passphrase", ["secret", os.fsdecode(b"p\xe4sswort-geheim")])
def test_a_passphrase_protected_key_signs(passphrase: str) -> None:
    signer_with_passphrase = DkimSigner(
        dkim_key().pem(passphrase), DOMAIN, SELECTOR, passphrase=passphrase
    )

    assert dkim_key().verifies(wire(signer_with_passphrase.sign(_email())))


@pytest.mark.parametrize(
    ("domain_name", "selector", "message"),
    [
        (
            "testdkim.example.net; s=x",
            SELECTOR,
            (
                'The DKIM domain name "testdkim.example.net; s=x" is not dot-separated labels '
                'of letters, digits, "-" and "_".'
            ),
        ),
        (
            DOMAIN,
            "s f\r\n",
            (
                'The DKIM selector "s f\\r\\n" is not dot-separated labels of letters, digits, '
                '"-" and "_".'
            ),
        ),
    ],
)
def test_a_domain_name_or_selector_that_is_not_dns_labels_is_refused(
    domain_name: str, selector: str, message: str
) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = DkimSigner(dkim_key().pem(), domain_name, selector)

    assert str(raised.value) == message


@pytest.mark.parametrize(
    ("private_key", "shown"),
    [
        pytest.param("file://a\x00b", "a\\x00b", id="a null byte"),
        pytest.param("file://a\ud800", "a\\ud800", id="a lone surrogate"),
    ],
)
def test_a_key_path_the_file_system_does_not_accept_is_refused(
    private_key: str, shown: str
) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = DkimSigner(private_key, DOMAIN, SELECTOR)

    assert str(raised.value) == (
        f'Unable to load DKIM private key: the file "{shown}" cannot be read: the path is not '
        "one the file system accepts."
    )


def test_without_the_extra_building_a_signer_names_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "dkim", None)
    monkeypatch.delitem(sys.modules, "xtr_mime.crypto._dkimpy", raising=False)

    with pytest.raises(LogicError) as raised:
        _ = signer()

    assert str(raised.value) == 'The "dkim" extra is required to use DKIM: uv add "xtr-mime[dkim]".'
