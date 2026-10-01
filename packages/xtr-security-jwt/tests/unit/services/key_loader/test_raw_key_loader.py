"""The raw key loader reads keys from text or files and derives the public one."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_security_core.exception import InvalidArgumentError

from tests.support.keys import RSA_PRIVATE_PEM, RSA_PUBLIC_PEM
from xtr_security_jwt.services.key_loader.abstract_key_loader import AbstractKeyLoader
from xtr_security_jwt.services.key_loader.key_dumper_interface import KeyDumperInterface
from xtr_security_jwt.services.key_loader.key_loader_interface import (
    TYPE_PRIVATE,
    TYPE_PUBLIC,
    KeyLoaderInterface,
)
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

if TYPE_CHECKING:
    from pathlib import Path


def test_it_implements_the_loader_and_dumper_interfaces() -> None:
    assert AbstractKeyLoader in RawKeyLoader.__mro__
    assert KeyLoaderInterface in RawKeyLoader.__mro__
    assert KeyDumperInterface in RawKeyLoader.__mro__


def test_it_reads_a_raw_private_key() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    assert loader.get_signing_key() == RSA_PRIVATE_PEM
    assert loader.load_key(TYPE_PRIVATE) == RSA_PRIVATE_PEM


def test_it_derives_the_public_key_from_the_private_one() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None)

    dumped = loader.load_key(TYPE_PUBLIC)

    assert "BEGIN PUBLIC KEY" in dumped


def test_it_returns_a_configured_public_key_as_is() -> None:
    loader = RawKeyLoader(None, RSA_PUBLIC_PEM)

    assert loader.load_key(TYPE_PUBLIC) == RSA_PUBLIC_PEM


def test_it_refuses_a_private_key_request_when_only_verifying() -> None:
    loader = RawKeyLoader(None, RSA_PUBLIC_PEM)

    with pytest.raises(InvalidArgumentError):
        _ = loader.load_key(TYPE_PRIVATE)


def test_it_refuses_to_dump_with_neither_key() -> None:
    loader = RawKeyLoader(None, None)

    with pytest.raises(InvalidArgumentError):
        _ = loader.dump_key()


def test_it_reads_a_key_from_a_file_path(tmp_path: Path) -> None:
    file = tmp_path / "key.pem"
    _ = file.write_text(RSA_PRIVATE_PEM, encoding="utf-8")
    loader = RawKeyLoader(str(file), None)

    assert loader.get_signing_key() == RSA_PRIVATE_PEM


def test_additional_public_keys_must_be_files(tmp_path: Path) -> None:
    missing = str(tmp_path / "absent.pem")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None, None, (missing,))

    with pytest.raises(InvalidArgumentError):
        _ = loader.get_additional_public_keys()


def test_additional_public_keys_are_read_from_their_files(tmp_path: Path) -> None:
    file = tmp_path / "extra.pem"
    _ = file.write_text(RSA_PUBLIC_PEM, encoding="utf-8")
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None, None, (str(file),))

    assert list(loader.get_additional_public_keys()) == [RSA_PUBLIC_PEM]


def test_it_reports_the_passphrase() -> None:
    loader = RawKeyLoader(RSA_PRIVATE_PEM, None, "secret")

    assert loader.get_passphrase() == "secret"
