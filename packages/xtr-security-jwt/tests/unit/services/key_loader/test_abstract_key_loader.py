"""The abstract loader reads a key as raw text or from the file a path names."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader.abstract_key_loader import AbstractKeyLoader

if TYPE_CHECKING:
    from pathlib import Path


class _Loader(AbstractKeyLoader):
    """A minimal concrete loader, so the shared behaviour can be exercised."""

    @override
    def load_key(self, key_type: str) -> str:
        del key_type
        return ""


def test_a_raw_signing_key_is_returned_as_is() -> None:
    loader = _Loader("raw-signing", "raw-public", "secret")

    assert loader.get_signing_key() == "raw-signing"
    assert loader.get_public_key() == "raw-public"
    assert loader.get_passphrase() == "secret"


def test_a_signing_key_given_as_a_path_is_read_from_the_file(tmp_path: Path) -> None:
    key_file = tmp_path / "signing.pem"
    _ = key_file.write_text("from-disk", encoding="utf-8")
    loader = _Loader(str(key_file), None)

    assert loader.get_signing_key() == "from-disk"


def test_a_key_file_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    loader = _Loader(str(tmp_path / "missing.pem"), None)

    with pytest.raises(InvalidArgumentError, match=r"missing\.pem' does not exist"):
        _ = loader.get_signing_key()


def test_a_missing_key_reports_none() -> None:
    loader = _Loader(None, None)

    assert loader.get_signing_key() is None
    assert loader.get_public_key() is None
    assert loader.get_passphrase() is None


def test_additional_public_keys_are_read_from_their_files(tmp_path: Path) -> None:
    first = tmp_path / "a.pem"
    _ = first.write_text("key-a", encoding="utf-8")
    loader = _Loader(None, None, None, (str(first),))

    assert loader.get_additional_public_keys() == ("key-a",)


def test_an_additional_public_key_that_is_not_a_file_is_refused() -> None:
    loader = _Loader(None, None, None, ("not-a-path",))

    with pytest.raises(InvalidArgumentError):
        _ = loader.get_additional_public_keys()
