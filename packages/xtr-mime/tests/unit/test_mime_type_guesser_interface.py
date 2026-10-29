"""Any object with both methods is a guesser: the interface is checked by shape."""

from __future__ import annotations

from xtr_mime import MimeTypeGuesserInterface


class _BothMethods:
    def is_guesser_supported(self) -> bool:
        return True

    def guess_mime_type(self, _path: str) -> str | None:
        return None


class _GuessOnly:
    def guess_mime_type(self, _path: str) -> str | None:
        return None


def test_an_object_with_both_methods_is_a_guesser() -> None:
    candidate: object = _BothMethods()

    assert isinstance(candidate, MimeTypeGuesserInterface)


def test_an_object_that_cannot_say_whether_it_runs_is_not() -> None:
    candidate: object = _GuessOnly()

    assert not isinstance(candidate, MimeTypeGuesserInterface)
