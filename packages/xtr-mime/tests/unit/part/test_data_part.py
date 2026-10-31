"""A data part: an attachment or an inline file, with a filename and a content id.

Upstream's serialization cases have no counterpart (a part is not serialized), nor has its
read from a URL (a file part reads a local path).
"""

from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import pytest

from tests.support.rendered_part import read_part
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.header import Headers, IdentificationHeader, ParameterizedHeader, UnstructuredHeader
from xtr_mime.part import DataPart, File

if TYPE_CHECKING:
    from xtr_mime.header import HeaderInterface

FIXTURES: Final = Path(__file__).parents[2] / "fixtures"
GIF: Final = FIXTURES / "mimetypes" / "test.gif"


def _headers(*headers: HeaderInterface) -> list[str]:
    return Headers(*headers).to_array()


def _attachment(name: str, disposition: str = "attachment") -> HeaderInterface:
    return ParameterizedHeader("Content-Disposition", disposition, {"name": name, "filename": name})


def _body(part: DataPart) -> bytes:
    return b"".join(part.body_to_iterable())


def test_constructor() -> None:
    part = DataPart("content")

    assert part.get_body() == "content"
    assert base64.b64decode(part.body_to_string()) == b"content"
    assert base64.b64decode(_body(part)) == b"content"
    # body_to_iterable() can be called several times.
    assert base64.b64decode(_body(part)) == b"content"
    assert part.get_media_type() == "application"
    assert part.get_media_subtype() == "octet-stream"

    html = DataPart("content", None, "text/html")
    assert html.get_media_type() == "text"
    assert html.get_media_subtype() == "html"


def test_constructor_with_resource() -> None:
    part = DataPart(io.BytesIO(b"content"))

    assert part.get_body() == b"content"
    assert base64.b64decode(part.body_to_string()) == b"content"
    assert base64.b64decode(_body(part)) == b"content"


def test_constructor_with_non_string_or_resource() -> None:
    with pytest.raises(TypeError):
        _ = DataPart(cast("str", object()))


def test_headers() -> None:
    assert DataPart("content").get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "application/octet-stream"),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        ParameterizedHeader("Content-Disposition", "attachment"),
    )
    part = DataPart("content", "photo.jpg", "text/html")
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/html", {"name": "photo.jpg"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        _attachment("photo.jpg"),
    )


def test_as_inline() -> None:
    part = DataPart("content", "photo.jpg", "text/html").as_inline()

    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/html", {"name": "photo.jpg"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        _attachment("photo.jpg", "inline"),
    )


def test_as_inline_with_cid() -> None:
    part = DataPart("content", "photo.jpg", "text/html").as_inline()
    cid = part.get_content_id()

    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "text/html", {"name": "photo.jpg"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        _attachment("photo.jpg", "inline"),
        IdentificationHeader("Content-ID", cid),
    )


def test_from_path() -> None:
    part = DataPart.from_path(GIF)
    content = GIF.read_bytes()

    assert part.get_body() == content
    assert base64.b64decode(part.body_to_string()) == content
    assert base64.b64decode(_body(part)) == content
    assert part.get_media_type() == "image"
    assert part.get_media_subtype() == "gif"
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "image/gif", {"name": "test.gif"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        _attachment("test.gif"),
    )


def test_from_path_with_meta() -> None:
    part = DataPart.from_path(GIF, "photo.gif", "image/jpeg")
    content = GIF.read_bytes()

    assert part.get_body() == content
    assert base64.b64decode(_body(part)) == content
    assert part.get_media_type() == "image"
    assert part.get_media_subtype() == "jpeg"
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "image/jpeg", {"name": "photo.gif"}),
        UnstructuredHeader("Content-Transfer-Encoding", "base64"),
        _attachment("photo.gif"),
    )


def test_from_path_with_encoding() -> None:
    part = DataPart.from_path(GIF, None, None, "8bit")

    # Adapted (D1): an 8bit body has its line breaks written as CRLF, as SMTP carries them.
    assert _body(part) == re.sub(rb"\r\n|\r|\n", b"\r\n", GIF.read_bytes())
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "image/gif", {"name": "test.gif"}),
        UnstructuredHeader("Content-Transfer-Encoding", "8bit"),
        _attachment("test.gif"),
    )


def test_from_path_with_invalid_encoding() -> None:
    with pytest.raises(InvalidArgumentError, match=re.escape('("foo" given)')):
        _ = DataPart.from_path(GIF, None, None, "foo")


def test_from_path_with_not_a_file() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = DataPart.from_path(FIXTURES / "mimetypes")


def test_from_path_does_not_read_the_file() -> None:
    part = DataPart.from_path(FIXTURES / "missing.pdf")

    assert part.get_content_type() == "application/pdf"
    assert part.get_filename() == "missing.pdf"


def test_binary_encoding_preserves_raw_bytes() -> None:
    body = b"\xff\xfe\x80\x00\x7f\xc3\xa9raw\x01payload"
    part = DataPart(body, "blob.bin", "application/octet-stream", "binary")

    assert part.body_to_string().encode("utf-8", "surrogateescape") == body
    assert _body(part) == body
    assert part.get_prepared_headers().to_array() == _headers(
        ParameterizedHeader("Content-Type", "application/octet-stream", {"name": "blob.bin"}),
        UnstructuredHeader("Content-Transfer-Encoding", "binary"),
        _attachment("blob.bin"),
    )


def test_has_content_id() -> None:
    part = DataPart("content")
    assert not part.has_content_id()

    _ = part.get_content_id()

    assert part.has_content_id()


def test_a_generated_content_id_is_random_hex_at_xtr() -> None:
    first, second = DataPart("content").get_content_id(), DataPart("content").get_content_id()

    assert re.fullmatch(r"[0-9a-f]{32}@xtr", first)
    assert first != second


def test_set_content_id() -> None:
    part = DataPart("content").set_content_id("test@test")

    assert part.has_content_id()
    assert part.get_content_id() == "test@test"
    assert read_part(part)["Content-ID"] == "<test@test>"


def test_set_content_id_invalid() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = DataPart("content").set_content_id("test")

    assert str(caught.value) == 'The "test" CID is invalid as it doesn\'t contain an "@".'


def test_get_filename() -> None:
    assert DataPart("content", None).get_filename() is None
    assert DataPart("content", "filename").get_filename() == "filename"


def test_get_content_type() -> None:
    assert DataPart("content").get_content_type() == "application/octet-stream"
    assert DataPart("content", None, "application/pdf").get_content_type() == "application/pdf"


def test_a_file_names_the_part_and_gives_its_type() -> None:
    part = DataPart(File(GIF, "logo.gif"))

    assert part.get_filename() == "logo.gif"
    assert part.get_content_type() == "image/gif"


def test_a_non_ascii_filename_reads_back() -> None:
    part = DataPart("content", "déjà vu.pdf", "application/pdf")

    assert read_part(part).get_filename() == "déjà vu.pdf"


def test_a_filename_looking_like_an_encoded_word_reads_back_as_given() -> None:
    part = DataPart(b"x", "=?utf-8?q?evil.exe?=")

    read = read_part(part)

    assert read.get_filename() == "=?utf-8?q?evil.exe?="
    assert read.get_param("name", header="content-disposition") == "=?utf-8?q?evil.exe?="
    assert b"=?" not in b"".join(part.to_iterable()).partition(b"\r\n\r\n")[0]


def test_as_debug_string() -> None:
    assert (
        DataPart("content", "photo.jpg", "image/jpeg").as_debug_string()
        == "image/jpeg disposition: attachment filename: photo.jpg"
    )
