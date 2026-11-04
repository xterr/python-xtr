"""A path is refused unless it names a regular file this process may read."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from xtr_mime._readable_file import ensure_readable_file
from xtr_mime.exception import InvalidArgumentError

if TYPE_CHECKING:
    from pathlib import Path


def test_a_readable_file_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "file"
    _ = path.write_bytes(b"")

    ensure_readable_file(str(path))


def test_a_missing_path_is_refused_by_name(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing")

    with pytest.raises(InvalidArgumentError) as raised:
        ensure_readable_file(missing)

    assert str(raised.value) == f'The "{missing}" file does not exist or is not readable.'


def test_a_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidArgumentError):
        ensure_readable_file(str(tmp_path))


def test_a_file_this_process_may_not_read_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "write-only"
    path.touch()
    path.chmod(0o333)
    if os.access(path, os.R_OK):
        pytest.skip("this user reads a file whatever its permissions")

    with pytest.raises(InvalidArgumentError):
        ensure_readable_file(str(path))


def test_a_path_with_a_null_byte_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        ensure_readable_file("picture\0.gif")
