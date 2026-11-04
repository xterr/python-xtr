"""A file a part reads only when it is rendered."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from xtr_mime.part import File

FIXTURES: Final = Path(__file__).parents[2] / "fixtures"


def test_the_path_is_kept_as_given() -> None:
    assert File(FIXTURES / "content.txt").get_path() == str(FIXTURES / "content.txt")


def test_the_content_type_comes_from_the_extension() -> None:
    assert File("/nowhere/report.PDF").get_content_type() == "application/pdf"


def test_an_unknown_extension_is_application_octet_stream() -> None:
    assert File("/nowhere/data.unknown-ext").get_content_type() == "application/octet-stream"
    assert File("/nowhere/data").get_content_type() == "application/octet-stream"


def test_the_size_is_read_from_the_file() -> None:
    assert File(FIXTURES / "content.txt").get_size() == len(b"content")


def test_the_filename_defaults_to_the_base_name() -> None:
    assert File("/nowhere/report.pdf").get_filename() == "report.pdf"
    assert File("/nowhere/report.pdf", "q3.pdf").get_filename() == "q3.pdf"
