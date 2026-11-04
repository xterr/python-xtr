"""What a guesser reading a file's content answers, as a test class a guesser's tests inherit.

A guesser's test class inherits :class:`MimeTypeGuesserTests` and defines a ``guesser`` fixture
that skips where the guesser cannot run. The files are tiny: a GIF with and without its
extension, a Word document, a CSV file and a single byte nothing recognises.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from xtr_mime.exception import InvalidArgumentError

if TYPE_CHECKING:
    from xtr_mime import MimeTypeGuesserInterface

__all__ = ["FIXTURES", "MimeTypeGuesserTests"]

FIXTURES: Final = Path(__file__).resolve().parent.parent / "fixtures" / "mimetypes"


class MimeTypeGuesserTests:
    """The answers every content-reading guesser gives for the fixture files."""

    def test_a_name_starting_with_a_dash_is_read_as_a_file(
        self, guesser: MimeTypeGuesserInterface, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(FIXTURES)

        assert guesser.guess_mime_type("-test") == "image/gif"

    def test_an_image_without_an_extension_is_recognised(
        self, guesser: MimeTypeGuesserInterface
    ) -> None:
        assert guesser.guess_mime_type(str(FIXTURES / "test")) == "image/gif"

    def test_an_image_with_its_extension_is_recognised(
        self, guesser: MimeTypeGuesserInterface
    ) -> None:
        assert guesser.guess_mime_type(str(FIXTURES / "test.gif")) == "image/gif"

    def test_content_nothing_recognises_is_arbitrary_data(
        self, guesser: MimeTypeGuesserInterface
    ) -> None:
        assert (
            guesser.guess_mime_type(str(FIXTURES / ".unknownextension"))
            == "application/octet-stream"
        )

    def test_a_type_libmagic_may_name_twice_is_named_once(
        self, guesser: MimeTypeGuesserInterface
    ) -> None:
        assert (
            guesser.guess_mime_type(str(FIXTURES / "test.docx"))
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    def test_a_directory_is_refused(
        self, guesser: MimeTypeGuesserInterface, tmp_path: Path
    ) -> None:
        with pytest.raises(InvalidArgumentError):
            _ = guesser.guess_mime_type(str(tmp_path))

    def test_a_missing_file_is_refused(self, guesser: MimeTypeGuesserInterface) -> None:
        with pytest.raises(InvalidArgumentError):
            _ = guesser.guess_mime_type(str(FIXTURES / "not_here"))

    def test_an_unreadable_file_is_refused(
        self, guesser: MimeTypeGuesserInterface, tmp_path: Path
    ) -> None:
        path = tmp_path / "to_delete"
        path.touch()
        path.chmod(0o333)
        if os.access(path, os.R_OK):
            pytest.skip("this user reads a file whatever its permissions")

        with pytest.raises(InvalidArgumentError):
            _ = guesser.guess_mime_type(str(path))
