"""The table of MIME types and extensions, and the guessers asked about a file's type.

The table is the standard library's built-in one — the same on every host, whatever its
``mime.types`` files hold — so the expected entries are ones it has from 3.11 on; where a case
names an entry it lacks, a comment says which and what stands in.
"""

from __future__ import annotations

import mimetypes
import sys
from typing import TYPE_CHECKING, Final, final

import pytest
from typing_extensions import override

from tests.support.fake_magic_module import FakeMagicModule
from tests.support.mime_type_guesser_conformance import FIXTURES, MimeTypeGuesserTests
from xtr_mime import (
    MagicMimeTypeGuesser,
    MimeTypeGuesserInterface,
    MimeTypes,
    MimeTypesInterface,
)
from xtr_mime.exception import InvalidArgumentError

if TYPE_CHECKING:
    from pathlib import Path

GIF: Final = str(FIXTURES / "test.gif")


@pytest.fixture
def without_libmagic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the libmagic guesser a new table registers unable to run, so the table answers."""
    monkeypatch.setitem(sys.modules, "magic", None)


@final
class _UnsupportedGuesser(MimeTypeGuesserInterface):
    """A guesser that cannot run here; asking it anyway fails the test."""

    @override
    def is_guesser_supported(self) -> bool:
        return False

    @override
    def guess_mime_type(self, path: str) -> str | None:
        pytest.fail("a guesser that cannot run was asked")


@final
class _AnsweringGuesser(MimeTypeGuesserInterface):
    """A guesser that answers every path with one type, or with no guess."""

    def __init__(self, answer: str | None) -> None:
        self._answer = answer

    @override
    def is_guesser_supported(self) -> bool:
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return self._answer


class TestMimeTypes(MimeTypeGuesserTests):
    """Where libmagic is installed, the guesser a new table registers reads the files."""

    @pytest.fixture
    def guesser(self) -> MimeTypeGuesserInterface:
        if not MagicMimeTypeGuesser().is_guesser_supported():
            pytest.skip("python-magic or libmagic is not installed")
        return MimeTypes()


def test_it_maps_types_and_guesses_them() -> None:
    mime_types: object = MimeTypes()

    assert isinstance(mime_types, MimeTypesInterface)
    assert isinstance(mime_types, MimeTypeGuesserInterface)


def test_a_guesser_that_cannot_run_is_never_asked() -> None:
    mime_types = MimeTypes()
    mime_types.register_guesser(_UnsupportedGuesser())

    # A file whose name carries its type: the answer holds with or without libmagic.
    assert mime_types.guess_mime_type(GIF) == "image/gif"


def test_get_extensions_lists_a_type_s_extensions_preferred_first() -> None:
    mime_types = MimeTypes()

    # The standard table has no "application/mbox"; PDF is a type with exactly one extension.
    assert mime_types.get_extensions("application/pdf") == ["pdf"]
    # The standard table lists its preferred extension first: "ps", then "ai" and "eps".
    assert mime_types.get_extensions("application/postscript") == ["ps", "ai", "eps"]
    assert "svg" in mime_types.get_extensions("image/svg+xml")
    # The standard table knows SVG by its registered name only, not as "image/svg".
    assert mime_types.get_extensions("image/svg") == []
    assert mime_types.get_extensions("application/whatever-unknown") == []


def test_get_mime_types_lists_an_extension_s_types_preferred_first() -> None:
    mime_types = MimeTypes()

    # The standard table has no "mbox"; "pdf" is an extension with exactly one type.
    assert mime_types.get_mime_types("pdf") == ["application/pdf"]
    assert "application/postscript" in mime_types.get_mime_types("ai")
    assert "application/postscript" in mime_types.get_mime_types("ps")
    # The standard table maps "svg" to the registered name only, without "image/svg".
    assert mime_types.get_mime_types("svg") == ["image/svg+xml"]
    assert mime_types.get_mime_types("notanextension") == []


def test_an_extra_map_adds_types_and_extensions() -> None:
    mime_types = MimeTypes({"text/bar": ["foo"], "text/baz": ["foo", "moof"]})

    assert "text/bar" in mime_types.get_mime_types("foo")
    assert "text/baz" in mime_types.get_mime_types("foo")
    assert mime_types.get_extensions("text/baz") == ["foo", "moof"]


def test_a_csv_file_is_named_with_a_type_whose_extension_is_csv() -> None:
    mime_types = MimeTypes()

    mime_type = mime_types.guess_mime_type(str(FIXTURES / "abc.csv"))

    assert mime_type in ("application/csv", "text/csv")
    assert mime_types.get_extensions(mime_type) == ["csv"]


def test_an_extra_map_ranks_before_the_standard_table() -> None:
    mime_types = MimeTypes({"image/x-gif": ["gif"], "application/pdf": ["pdfa", "pdf"]})

    assert mime_types.get_mime_types("gif") == ["image/x-gif", "image/gif"]
    assert mime_types.get_extensions("application/pdf") == ["pdfa", "pdf"]


def test_a_common_type_ranks_after_the_registered_one() -> None:
    mime_types = MimeTypes()

    assert mime_types.get_mime_types("jpg") == ["image/jpeg", "image/jpg"]
    assert mime_types.get_extensions("image/jpg") == ["jpg"]


def test_a_lookup_falls_back_to_lower_case() -> None:
    mime_types = MimeTypes()

    assert mime_types.get_mime_types("PDF") == ["application/pdf"]
    assert mime_types.get_extensions("Application/PDF") == ["pdf"]


def test_every_entry_of_the_standard_table_is_known() -> None:
    standard = mimetypes.MimeTypes()
    mime_types = MimeTypes()

    for types_map in standard.types_map:
        for dotted_extension, mime_type in types_map.items():
            extension = dotted_extension.removeprefix(".")
            assert mime_type in mime_types.get_mime_types(extension)
            assert extension in mime_types.get_extensions(mime_type)


def test_a_returned_list_is_the_caller_s_own() -> None:
    mime_types = MimeTypes()

    mime_types.get_extensions("application/pdf").append("pdfx")
    mime_types.get_mime_types("pdf").append("application/x-pdf")

    assert mime_types.get_extensions("application/pdf") == ["pdf"]
    assert mime_types.get_mime_types("pdf") == ["application/pdf"]


def test_the_last_registered_guesser_is_asked_first() -> None:
    mime_types = MimeTypes()
    mime_types.register_guesser(_AnsweringGuesser("text/first"))
    mime_types.register_guesser(_AnsweringGuesser("text/last"))

    assert mime_types.guess_mime_type(GIF) == "text/last"


def test_a_guesser_without_an_answer_hands_over_to_the_next() -> None:
    mime_types = MimeTypes()
    mime_types.register_guesser(_AnsweringGuesser("text/first"))
    mime_types.register_guesser(_AnsweringGuesser(None))

    assert mime_types.guess_mime_type(GIF) == "text/first"


def test_libmagic_is_asked_before_the_table(monkeypatch: pytest.MonkeyPatch) -> None:
    # The stand-in for libmagic disagrees with the file's name, and wins.
    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule("image/png"))

    assert MimeTypes().guess_mime_type(GIF) == "image/png"


@pytest.mark.usefixtures("without_libmagic")
def test_it_can_always_guess() -> None:
    assert MimeTypes().is_guesser_supported()


@pytest.mark.usefixtures("without_libmagic")
def test_a_file_no_guesser_can_read_is_named_by_its_extension() -> None:
    assert MimeTypes().guess_mime_type(GIF) == "image/gif"


@pytest.mark.usefixtures("without_libmagic")
def test_an_extension_in_capitals_is_looked_up_in_lower_case(tmp_path: Path) -> None:
    path = tmp_path / "PICTURE.GIF"
    _ = path.write_bytes(b"GIF87a")

    assert MimeTypes().guess_mime_type(str(path)) == "image/gif"


@pytest.mark.usefixtures("without_libmagic")
@pytest.mark.parametrize("name", ["test", ".unknownextension"])
def test_a_file_whose_extension_names_no_type_gets_no_guess(name: str) -> None:
    assert MimeTypes().guess_mime_type(str(FIXTURES / name)) is None


@pytest.mark.usefixtures("without_libmagic")
def test_the_extension_names_only_a_readable_file(tmp_path: Path) -> None:
    missing = str(tmp_path / "missing.gif")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = MimeTypes().guess_mime_type(missing)

    assert str(raised.value) == f'The "{missing}" file does not exist or is not readable.'


def test_get_default_builds_one_table_and_keeps_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MimeTypes, "_default", None)

    default = MimeTypes.get_default()

    assert MimeTypes.get_default() is default


def test_set_default_replaces_the_shared_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(MimeTypes, "_default", None)
    mime_types = MimeTypes({"text/x-custom": ["custom"]})

    MimeTypes.set_default(mime_types)

    assert MimeTypes.get_default() is mime_types
