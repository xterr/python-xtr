"""The libmagic guesser reads real files where libmagic is installed.

Everywhere else its own logic — when it may run, what it asks libmagic, how it reads the answer
and the failures — runs against a stand-in for the ``magic`` module.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final

import pytest

from tests.support.fake_magic_module import FakeMagicError, FakeMagicModule
from tests.support.mime_type_guesser_conformance import FIXTURES, MimeTypeGuesserTests
from xtr_mime import MagicMimeTypeGuesser, MimeTypeGuesserInterface
from xtr_mime.exception import InvalidArgumentError, LogicError, MimeRuntimeError

if TYPE_CHECKING:
    from pathlib import Path

GIF: Final = str(FIXTURES / "test.gif")


class TestMagicMimeTypeGuesser(MimeTypeGuesserTests):
    @pytest.fixture
    def guesser(self) -> MimeTypeGuesserInterface:
        guesser = MagicMimeTypeGuesser()
        if not guesser.is_guesser_supported():
            pytest.skip("python-magic or libmagic is not installed")
        return guesser


def test_it_is_a_mime_type_guesser() -> None:
    guesser: object = MagicMimeTypeGuesser()

    assert isinstance(guesser, MimeTypeGuesserInterface)


def test_it_is_not_supported_without_python_magic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "magic", None)

    assert not MagicMimeTypeGuesser().is_guesser_supported()


def test_it_is_not_supported_when_libmagic_fails_to_load(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A binding that opens libmagic as it is imported, failing as a missing library does.
    _ = (tmp_path / "magic.py").write_text('raise OSError("libmagic.so.1: cannot open")\n')
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    monkeypatch.delitem(sys.modules, "magic", raising=False)

    assert not MagicMimeTypeGuesser().is_guesser_supported()


def test_it_is_supported_when_the_magic_module_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule("image/gif"))

    assert MagicMimeTypeGuesser().is_guesser_supported()


def test_whether_it_is_supported_is_decided_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "magic", None)
    guesser = MagicMimeTypeGuesser()
    _ = guesser.is_guesser_supported()

    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule("image/gif"))

    assert not guesser.is_guesser_supported()


def test_it_asks_libmagic_for_the_mime_type_of_the_file(monkeypatch: pytest.MonkeyPatch) -> None:
    magic = FakeMagicModule("image/gif")
    monkeypatch.setitem(sys.modules, "magic", magic)

    assert MagicMimeTypeGuesser().guess_mime_type(GIF) == "image/gif"
    assert magic.calls == [(GIF, True)]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("application/pdfapplication/pdf", "application/pdf"),
        ("text/plain", "text/plain"),
        ("image/gif", "image/gif"),
    ],
)
def test_a_type_libmagic_names_twice_in_a_row_is_named_once(
    monkeypatch: pytest.MonkeyPatch, answer: str, expected: str
) -> None:
    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule(answer))

    assert MagicMimeTypeGuesser().guess_mime_type(GIF) == expected


def test_an_empty_answer_is_no_guess(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule(""))

    assert MagicMimeTypeGuesser().guess_mime_type(GIF) is None


def test_a_libmagic_failure_is_a_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    failure = FakeMagicError("could not find any valid magic files!")
    monkeypatch.setitem(sys.modules, "magic", FakeMagicModule(failure))

    with pytest.raises(MimeRuntimeError) as raised:
        _ = MagicMimeTypeGuesser().guess_mime_type(GIF)

    assert str(raised.value) == f'libmagic could not guess the MIME type of the "{GIF}" file.'
    assert raised.value.__cause__ is failure


def test_guessing_where_it_cannot_run_is_a_logic_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "magic", None)

    with pytest.raises(LogicError) as raised:
        _ = MagicMimeTypeGuesser().guess_mime_type(GIF)

    assert str(raised.value) == 'The "MagicMimeTypeGuesser" guesser is not supported.'


def test_the_path_is_checked_before_whether_it_can_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(sys.modules, "magic", None)
    missing = str(tmp_path / "missing.gif")

    with pytest.raises(InvalidArgumentError) as raised:
        _ = MagicMimeTypeGuesser().guess_mime_type(missing)

    assert str(raised.value) == f'The "{missing}" file does not exist or is not readable.'


def test_libmagic_is_not_asked_about_a_path_that_is_not_a_readable_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    magic = FakeMagicModule("image/gif")
    monkeypatch.setitem(sys.modules, "magic", magic)

    with pytest.raises(InvalidArgumentError):
        _ = MagicMimeTypeGuesser().guess_mime_type(str(tmp_path))

    assert magic.calls == []
