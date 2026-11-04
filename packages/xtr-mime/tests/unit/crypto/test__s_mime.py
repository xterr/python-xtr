"""What cryptography writes is read back into a part; certificates and keys are read from files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_mime.crypto._s_mime import read_part, read_pem_file
from xtr_mime.exception import MimeRuntimeError

if TYPE_CHECKING:
    from pathlib import Path

# What cryptography writes for an enveloped message: its lines end in a bare line feed.
_ENVELOPED = (
    b"MIME-Version: 1.0\n"
    b'Content-Disposition: attachment; filename="smime.p7m"\n'
    b'Content-Type: application/pkcs7-mime; smime-type="enveloped-data"; name="smime.p7m"\n'
    b"Content-Transfer-Encoding: base64\n"
    b"\n"
    b"MIIB6QYJKoZIhvcNAQcDoIIB2jCCAdYCAQAx\n"
    b"BAMMAWECFEE7z8lJnzdwPYOtvUSMhN1j2Ro+\n"
)


def test_the_part_takes_the_media_type_and_parameters_written() -> None:
    part = read_part(_ENVELOPED)

    headers = part.get_prepared_headers()
    assert headers.get_header_body("Content-Type") == "application/pkcs7-mime"
    assert headers.get_header_parameter("Content-Type", "smime-type") == "enveloped-data"
    assert headers.get_header_parameter("Content-Type", "name") == "smime.p7m"


def test_the_other_headers_written_are_left_out() -> None:
    assert read_part(_ENVELOPED).get_prepared_headers().get_names() == ["content-type"]


def test_the_body_is_kept_with_its_lines_ending_in_crlf() -> None:
    assert read_part(_ENVELOPED).body_to_string() == (
        "MIIB6QYJKoZIhvcNAQcDoIIB2jCCAdYCAQAx\r\nBAMMAWECFEE7z8lJnzdwPYOtvUSMhN1j2Ro+\r\n"
    )


@pytest.mark.parametrize("prefix", ["", "file://"])
def test_a_file_is_read_from_its_path(tmp_path: Path, prefix: str) -> None:
    path = tmp_path / "a.pem"
    _ = path.write_bytes(b"pem")

    file = read_pem_file(f"{prefix}{path}")

    assert (file.path, file.content) == (str(path), b"pem")


def test_the_content_of_a_file_is_not_shown(tmp_path: Path) -> None:
    path = tmp_path / "a.key"
    _ = path.write_bytes(b"secret key")

    assert "secret key" not in repr(read_pem_file(path))


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MimeRuntimeError) as raised:
        _ = read_pem_file(tmp_path / "missing\n.pem")

    assert str(raised.value) == f'File does not exist: "{tmp_path}/missing\\n.pem".'


def test_a_file_that_cannot_be_read_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MimeRuntimeError) as raised:
        _ = read_pem_file(tmp_path)

    assert str(raised.value) == f'Unable to read the file "{tmp_path}": Is a directory.'


@pytest.mark.parametrize(
    ("path", "shown"),
    [
        pytest.param("a\x00b", "a\\x00b", id="a null byte"),
        pytest.param("file://\x00", "\\x00", id="a null byte after file://"),
        pytest.param("a\ud800", "a\\ud800", id="a lone surrogate"),
    ],
)
def test_a_path_the_file_system_does_not_accept_is_refused(path: str, shown: str) -> None:
    with pytest.raises(MimeRuntimeError) as raised:
        _ = read_pem_file(path)

    assert str(raised.value) == (
        f'Unable to read the file "{shown}": the path is not one the file system accepts.'
    )
