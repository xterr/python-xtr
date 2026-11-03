"""Text, data and S/MIME parts as a queued email carries them: by content, never by path."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from xtr_mime import DataPart, SMimePart, TextPart

from xtr_mailer.exception import InvalidArgumentError
from xtr_mailer.messenger._wire._json import encoded
from xtr_mailer.messenger._wire._parts import read_leaf, write_leaf

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_mime import AbstractPart


def _back(part: AbstractPart) -> AbstractPart:
    written = write_leaf(part)
    assert written is not None
    return read_leaf(written, "part")


def _rendered(part: AbstractPart) -> bytes:
    return b"".join(part.to_iterable())


def test_a_text_part_comes_back_with_its_charset_subtype_and_encoding() -> None:
    part = TextPart("<p>Grüße</p>", "iso-8859-1", "html", "base64")
    _ = part.set_disposition("inline").set_name("greeting")
    _ = part.get_headers().add_text_header("X-Part", "1")

    back = _back(part)

    assert type(back) is TextPart
    assert _rendered(back) == _rendered(part)
    assert back.get_headers().get_header_body("X-Part") == "1"


def test_a_text_part_of_bytes_comes_back_bytes() -> None:
    back = _back(TextPart(b"\xff\x00", None))

    assert isinstance(back, TextPart)
    assert back.get_body() == b"\xff\x00"


def test_a_data_part_comes_back_with_its_filename_type_and_content_id() -> None:
    part = DataPart(b"\x89PNG", "logo.png", "image/png").as_inline().set_content_id("l@example")

    back = _back(part)

    assert type(back) is DataPart
    assert _rendered(back) == _rendered(part)
    assert back.get_content_id() == "l@example"


def test_a_data_part_without_a_content_id_gets_none_made_up_on_the_way() -> None:
    back = _back(DataPart("text", "a.txt"))

    assert isinstance(back, DataPart)
    assert not back.has_content_id()


def test_a_file_is_read_when_the_email_is_queued_and_travels_as_its_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "report.pdf"
    _ = path.write_bytes(b"%PDF-1.4")
    part = DataPart.from_path(path)

    written = write_leaf(part)
    path.unlink()

    assert written is not None
    assert str(tmp_path) not in repr(written)
    back = read_leaf(written, "part")
    assert isinstance(back, DataPart)
    assert (back.get_body(), back.get_filename(), back.get_content_type()) == (
        b"%PDF-1.4",
        "report.pdf",
        "application/pdf",
    )


def test_a_stream_is_read_when_the_email_is_queued() -> None:
    back = _back(DataPart(io.BytesIO(b"streamed"), "s.bin"))

    assert isinstance(back, DataPart)
    assert back.get_body() == b"streamed"


def test_an_s_mime_part_comes_back_byte_for_byte() -> None:
    part = SMimePart(b"opaque\r\nbytes\r\n", "application", "pkcs7-mime", {"smime-type": "x"})

    back = _back(part)

    assert type(back) is SMimePart
    assert _rendered(back) == _rendered(part)


def test_a_part_that_is_not_a_leaf_is_left_to_the_caller() -> None:
    class _Custom(TextPart):
        pass

    assert write_leaf(_Custom("x")) is None


@pytest.mark.parametrize("data", [{"$type": "x-evil"}, ["text"], None])
def test_a_part_of_a_kind_the_queue_does_not_carry_is_refused(data: object) -> None:
    with pytest.raises(InvalidArgumentError, match="part is not a part of a class"):
        _ = read_leaf(data, "part")


def _data(**changed: object) -> dict[str, object]:
    written = write_leaf(DataPart(b"x", "a.bin"))
    assert written is not None
    return {**written, **changed}


@pytest.mark.parametrize(
    "changed",
    [
        {"path": "/etc/passwd"},
        {"body": {"path": "/etc/passwd"}},
        {"body": {"bytes": "not base64!"}},
        {"encoding": "x-evil"},
        {"content_id": "no-at-sign"},
        {"content_type": 3},
    ],
    ids=["path field", "path body", "base64", "encoding", "content id", "content type"],
)
def test_a_part_its_fields_or_its_class_refuse_is_refused(changed: dict[str, object]) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = read_leaf(_data(**changed), "part")

    assert str(raised.value).startswith("The queued email cannot be read: part")
    assert "passwd" not in str(raised.value)


def test_a_data_part_body_is_never_read_from_a_path(tmp_path: Path) -> None:
    secret = tmp_path / "secret"
    _ = secret.write_bytes(b"do not read")
    written = _data(body={"text": str(secret)})

    back = read_leaf(written, "part")

    assert isinstance(back, DataPart)
    assert back.get_body() == str(secret)
    assert encoded(b"do not read") not in repr(written)
