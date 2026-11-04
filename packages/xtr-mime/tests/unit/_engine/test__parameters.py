"""Parameterized headers: parameters that read back as given, whatever they hold."""

from __future__ import annotations

import random
from email import message_from_bytes
from email import policy as stdlib_policy
from email.headerregistry import HeaderRegistry
from email.parser import HeaderParser

import pytest

from tests.support.engine_cases import (
    CONTROL_CHARACTERS,
    INJECTED_FILENAME,
    lines_of,
    read_parameter,
    text_leaf,
)
from tests.support.wire import decode_anywhere, readings
from xtr_mime import _engine
from xtr_mime._engine import BinaryLeaf, Parameterized
from xtr_mime._engine._policy import POLICY
from xtr_mime.exception import RfcComplianceError


def test_a_non_ascii_parameter_is_rfc_2231_encoded_and_decodes_back() -> None:
    value = Parameterized("attachment", {"filename": 'résumé "final".pdf'})

    field = _engine.fold_header("Content-Disposition", value)

    assert field.isascii()
    assert "filename*=" in field
    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    assert parsed.get_filename() == 'résumé "final".pdf'
    assert parsed.get_content_disposition() == "attachment"


def test_a_content_type_keeps_its_parameters() -> None:
    field = _engine.fold_header(
        "Content-Type", Parameterized("text/plain", {"charset": "utf-8", "name": "a.txt"})
    )

    parsed = HeaderParser(policy=stdlib_policy.default).parsestr(field + "\r\n\r\n")
    assert parsed.get_content_type() == "text/plain"
    assert parsed.get_param("charset") == "utf-8"
    assert parsed.get_param("name") == "a.txt"


LOOKALIKE_FILENAMES = [
    "=?utf-8?q?evil.exe?=",
    "invoice=?utf-8?q?evil.exe?=",
    "=?utf-8?b?ZXZpbC5leGU=?=.pdf",
    "=?utf-8?q?a?= =?utf-8?q?b?=",
    "=?utf-8?x?a?==?utf-8?q?evil.exe?=",
    "résumé =?utf-8?q?evil.exe?=",
    "=?utf-8?q?evil.exe?=" * 12,
]


@pytest.mark.parametrize("filename", LOOKALIKE_FILENAMES)
def test_a_filename_looking_like_an_encoded_word_reads_back_as_given(filename: str) -> None:
    field = _engine.fold_header(
        "Content-Disposition", Parameterized("attachment", {"filename": filename})
    )

    reader, param, words = read_parameter(field, "content-disposition", "filename")
    assert (reader, param) == (filename, filename)
    # Nothing in the field is taken for an encoded word, however leniently it is read.
    assert "=?" not in field
    assert words == field.replace("\r\n", "")
    assert all(len(line) <= 76 for line in lines_of(field))


@pytest.mark.parametrize("name", LOOKALIKE_FILENAMES)
def test_a_content_type_name_looking_like_an_encoded_word_reads_back_as_given(name: str) -> None:
    field = _engine.fold_header(
        "Content-Type", Parameterized("text/plain", {"charset": "utf-8", "name": name})
    )

    _, param, _ = read_parameter(field, "content-type", "name")
    parsed = message_from_bytes(f"{field}\r\n\r\nx".encode(), policy=stdlib_policy.default)
    assert param == name
    assert parsed.get_content_type() == "text/plain"
    assert parsed.get_param("charset") == "utf-8"
    assert "=?" not in field


def test_an_attachment_named_like_an_encoded_word_keeps_its_name_on_the_wire() -> None:
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        disposition=Parameterized("attachment", {"filename": "=?utf-8?q?evil.exe?="}),
    )

    parsed = message_from_bytes(
        _engine.to_bytes(_engine.build_binary(leaf)), policy=stdlib_policy.default
    )

    assert parsed.get_filename() == "=?utf-8?q?evil.exe?="


def test_parameters_written_by_hand_that_would_not_read_back_are_refused() -> None:
    # A reader matches parameter names case-insensitively: one of the two is lost.
    value = Parameterized("attachment", {"filename": "=?utf-8?q?a?=", "FILENAME": "b"})

    with pytest.raises(RfcComplianceError, match="read back to the parameters"):
        _ = _engine.fold_header("Content-Disposition", value)


@pytest.mark.parametrize("filename", ["a.txt", "résumé.pdf", "x" * 120 + ".txt"])
def test_a_filename_without_an_encoded_word_opening_is_written_as_the_package_writes_it(
    filename: str,
) -> None:
    value = Parameterized("attachment", {"filename": filename})
    package = HeaderRegistry()("Content-Disposition", f'attachment; filename="{filename}"')

    assert _engine.fold_header("Content-Disposition", value) + "\r\n" == package.fold(policy=POLICY)


def test_a_line_break_in_a_disposition_filename_is_refused_on_the_wire() -> None:
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        disposition=Parameterized("attachment", {"filename": INJECTED_FILENAME}),
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


@pytest.mark.parametrize("control", CONTROL_CHARACTERS)
def test_a_control_character_in_a_content_type_parameter_is_refused(control: str) -> None:
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        parameters={"name": f"a{control}b"},
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


def test_a_control_character_in_a_text_leaf_parameter_is_refused() -> None:
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.build_text(text_leaf(parameters={"name": INJECTED_FILENAME}))


@pytest.mark.parametrize(
    "name", ["", "file name", "a\r\nb", "x*", "x'", "x%", "a=b", 'a"b', "a;b", "nàme", "a\x00"]
)
def test_a_parameter_name_that_is_not_an_rfc_2231_token_is_refused(name: str) -> None:
    with pytest.raises(RfcComplianceError, match="parameter name"):
        _ = _engine.fold_header("Content-Disposition", Parameterized("attachment", {name: "x"}))


@pytest.mark.parametrize("value", ["", "attach ment", "a\r\nb", "a;b", "inlïne"])
def test_a_disposition_that_is_not_a_token_is_refused(value: str) -> None:
    with pytest.raises(RfcComplianceError, match="token"):
        _ = _engine.fold_header("Content-Disposition", Parameterized(value))


@pytest.mark.parametrize("value", ["text", "text/", "/plain", "text/pl ain", "a/b/c", "té/x"])
def test_a_content_type_that_is_not_type_slash_subtype_is_refused(value: str) -> None:
    with pytest.raises(RfcComplianceError, match="media type"):
        _ = _engine.fold_header("Content-Type", Parameterized(value))


def test_a_long_content_type_that_is_no_media_type_is_shown_cut() -> None:
    value = "application/" + "x" * 530 + " y"

    with pytest.raises(RfcComplianceError) as raised:
        _ = _engine.fold_header("Content-Type", Parameterized(value))

    assert str(raised.value) == f'"{value[:64]}…" is not a media type: type/subtype.'


@pytest.mark.parametrize(
    "filename",
    [
        "=?utf-8?q?x=0BContent-Type:_text/html?=",
        "=?utf-8?q?x=0D=0ABcc:_evil@attacker.com?=",
        "=?utf-8?b?eAtCY2M6IGV2aWxAYXR0YWNrZXIuY29t?=",
        "=?utf-8?q?x=E2=80=A8y?=",
    ],
)
def test_an_encoded_word_in_a_parameter_decoding_to_a_control_character_is_refused(
    filename: str,
) -> None:
    disposition = Parameterized("attachment", {"filename": filename})
    leaf = BinaryLeaf(
        content=b"x",
        maintype="application",
        subtype="octet-stream",
        transfer_encoding="base64",
        disposition=disposition,
    )

    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Content-Disposition", disposition)
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.fold_header("Content-Type", Parameterized("text/plain", {"name": filename}))
    with pytest.raises(RfcComplianceError, match="control character"):
        _ = _engine.to_bytes(_engine.build_binary(leaf))


_LOOKALIKE_PIECES = (
    "=?", "?=", "=?utf-8?q?", "=?utf-8?b?", "=?utf-8?x?", "=?=", "?q?", "?b?", "=0D=0A", "=3F",
    "aGk=", "Bcc:_v@e.x", "_", "a", "Ž", "%", "'", ";", "=", "?", "x" * 40, "t" * 80, " ",
)  # fmt: skip


def _lookalike(rng: random.Random) -> str:
    text = "".join(rng.choice(_LOOKALIKE_PIECES) for _ in range(rng.randint(1, 8)))
    return text.strip(" ") or "a"


def test_no_reader_decodes_a_part_of_a_header_word_looking_like_an_encoded_word() -> None:
    """A seeded fuzz: a text header and a parameter read back as given, to every reader."""
    rng = random.Random(20261101)  # noqa: S311 -- a reproducible fuzz, not a secret
    written = 0

    for _ in range(2500):
        text, filename = _lookalike(rng), _lookalike(rng)
        try:
            field = _engine.fold_header("Subject", text)
        except RfcComplianceError:
            # Refused only when the engine's own reading decodes to a control character.
            assert "=?" in text
        else:
            written += 1
            assert readings(field) == (text, text, text)
        try:
            field = _engine.fold_header(
                "Content-Disposition", Parameterized("attachment", {"filename": filename})
            )
        except RfcComplianceError:
            assert "=?" in filename
        else:
            written += 1
            reader, param, words = read_parameter(field, "content-disposition", "filename")
            assert (reader, param) == (filename, filename)
            unfolded = field.replace("\r\n", "")
            assert words == unfolded
            assert decode_anywhere(field) == unfolded.split(":", 1)[1].strip()

    assert written > 4500
