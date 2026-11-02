"""A part tree written to the wire, in pieces or whole, and wire bytes read back."""

from __future__ import annotations

import random
from datetime import UTC, datetime

import pytest

from tests.support.engine_cases import FUZZ_PIECES, LONG_SUBJECT, text_leaf
from xtr_mime import _engine
from xtr_mime._engine import BinaryLeaf, Mailbox, Parameterized
from xtr_mime.exception import MimeError, MimeRuntimeError, RfcComplianceError


def test_parsing_pathologically_nested_input_is_a_mime_runtime_error() -> None:
    data = b"".join(
        b"Content-Type: multipart/mixed; boundary=b%d\r\n\r\n--b%d\r\n" % (level, level)
        for level in range(2000)
    )

    with pytest.raises(MimeRuntimeError, match="nested"):
        _ = _engine.parse(data + b"\r\nx\r\n")


def test_a_parsed_multipart_with_an_empty_boundary_is_refused_when_rendered() -> None:
    """The engine would make up a boundary and rewrite Content-Type from what it decoded."""
    parsed = _engine.parse(
        b'Content-Type: multipart/mixed; boundary=""; name="=?utf-8?q?a=00b?="\r\n\r\n'
        b"--\r\nContent-Type: text/plain\r\n\r\nhi\r\n----\r\n"
    )

    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.to_bytes(parsed)


def test_a_multipart_whose_fields_drop_the_boundary_is_refused_when_rendered() -> None:
    multipart = _engine.build_multipart("mixed", "b", [_engine.build_text(text_leaf())])
    _engine.set_fields(multipart, ["Content-Type: multipart/mixed"])

    with pytest.raises(RfcComplianceError, match="boundary"):
        _ = _engine.to_bytes(multipart)


def test_only_the_engine_errors_ever_escape_parsing_and_rendering_bytes() -> None:
    rng = random.Random(29102026)  # noqa: S311 -- a reproducible fuzz, not a secret
    pieces = [piece.encode("utf-8", "surrogatepass") for piece in FUZZ_PIECES]
    pieces += [b"\r\n", b"X-A: ", b"Content-Type: multipart/mixed; boundary=b\r\n", b"--b\r\n"]

    for _ in range(500):
        data = b"".join(rng.choice(pieces) for _ in range(rng.randint(0, 40)))
        try:
            _ = _engine.to_bytes(_engine.parse(data))
        except MimeError:
            continue


def _sample_message() -> _engine.EnginePart:
    alternative = _engine.build_multipart(
        "alternative",
        "alt_boundary",
        [
            _engine.build_text(text_leaf("Héllo wörld")),
            _engine.build_text(
                text_leaf("<p>Héllo</p>", subtype="html", transfer_encoding="base64")
            ),
        ],
    )
    attachment = _engine.build_binary(
        BinaryLeaf(
            content=b"%PDF-1.4\x00\xff" * 40,
            maintype="application",
            subtype="pdf",
            transfer_encoding="base64",
            disposition=Parameterized("attachment", {"filename": "résumé.pdf"}),
        )
    )
    body = _engine.build_multipart("mixed", "mixed_boundary", [alternative, attachment])
    return _engine.build_message(
        [
            ("From", [Mailbox("Žluťoučký Kůň", "alice@dømi.fo")]),
            ("Subject", LONG_SUBJECT),
            ("Date", datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)),
            ("MIME-Version", "1.0"),
        ],
        body,
    )


def test_parsing_a_rendered_message_gives_back_its_structure_and_content() -> None:
    parsed = _engine.parse(_engine.to_bytes(_sample_message()))

    assert parsed.get_content_type() == "multipart/mixed"
    assert parsed["Subject"] == LONG_SUBJECT
    assert str(parsed["From"]) == "Žluťoučký Kůň <alice@xn--dmi-0na.fo>"
    alternative, attachment = parsed.iter_parts()
    text, html = alternative.iter_parts()
    assert alternative.get_boundary() == "alt_boundary"
    # Read back from the wire, a text body has the wire's CRLF line ends.
    assert text.get_content() == "Héllo wörld\r\n"
    assert html.get_content() == "<p>Héllo</p>\r\n"
    assert attachment.get_filename() == "résumé.pdf"
    assert attachment.get_content() == b"%PDF-1.4\x00\xff" * 40


def test_a_rendered_message_is_ascii_with_crlf_lines_of_at_most_76() -> None:
    raw = _engine.to_bytes(_sample_message())

    assert raw.isascii()
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert all(len(line) <= 76 for line in raw.split(b"\r\n"))


def test_a_body_line_starting_with_from_is_not_escaped() -> None:
    raw = _engine.to_bytes(_engine.build_text(text_leaf("From here on", transfer_encoding="8bit")))

    assert raw.endswith(b"\r\n\r\nFrom here on\r\n")


def test_the_rendered_chunks_join_to_the_rendered_string() -> None:
    message = _sample_message()

    chunks = list(_engine.render(message))

    assert len(chunks) > 1
    assert all(type(chunk) is bytes for chunk in chunks)
    assert b"".join(chunks) == _engine.to_bytes(message)
    assert b"".join(chunks) == _engine.to_string(message).encode("utf-8", "surrogateescape")


def test_an_eight_bit_body_in_another_charset_survives_to_string() -> None:
    part = _engine.build_text(text_leaf("Žluť", charset="iso-8859-2", transfer_encoding="8bit"))

    rendered = _engine.to_string(part)

    assert rendered.encode("utf-8", "surrogateescape") == _engine.to_bytes(part)
    assert _engine.to_bytes(part).endswith("Žluť\r\n".encode("iso-8859-2"))


# What a reader and writer would change: a fold before a long word, the whitespace after a
# colon, a bare CR, a boundary line with trailing spaces, bytes that are not UTF-8.
_VERBATIM_BODY = (
    b"--b  \r\nX-Token:\r\n " + b"t" * 80 + b"\r\nX-A:   v\r\nX-C: a\rb\r\n\r\n\xe9\xff\r\n--b--"
)


@pytest.mark.parametrize("content_type", ["multipart/signed", "text/plain", "message/rfc822"])
def test_a_verbatim_part_writes_its_headers_then_its_body_unchanged(content_type: str) -> None:
    part = _engine.build_verbatim(_VERBATIM_BODY)
    _engine.set_fields(part, [f'Content-Type: {content_type}; boundary="b"'])

    rendered = _engine.to_bytes(part)

    assert rendered == f'Content-Type: {content_type}; boundary="b"\r\n\r\n'.encode() + (
        _VERBATIM_BODY
    )


def test_a_message_around_a_verbatim_body_writes_the_body_unchanged() -> None:
    body = _engine.build_verbatim(_VERBATIM_BODY)
    _engine.set_fields(body, ['Content-Type: multipart/signed; boundary="b"'])

    message = _engine.build_message([("Subject", "Hi")], body)

    assert _engine.to_bytes(message).endswith(b'boundary="b"\r\n\r\n' + _VERBATIM_BODY)


def test_a_verbatim_part_inside_a_multipart_is_written_unchanged() -> None:
    child = _engine.build_verbatim(_VERBATIM_BODY)
    _engine.set_fields(child, ['Content-Type: multipart/signed; boundary="b"'])

    rendered = _engine.to_bytes(_engine.build_multipart("mixed", "outer", [child]))

    assert b'boundary="b"\r\n\r\n' + _VERBATIM_BODY + b"\r\n--outer--" in rendered
