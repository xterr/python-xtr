"""A stand-in for the ``magic`` module python-magic installs, for hosts without libmagic."""

from __future__ import annotations

from types import ModuleType
from typing import ClassVar

__all__ = ["FakeMagicError", "FakeMagicModule"]


class FakeMagicError(Exception):
    """Stands in for ``magic.MagicException``, which a libmagic failure is raised as."""


class FakeMagicModule(ModuleType):
    """Answers every ``from_file`` with the type it was built with, or raises its error.

    Put in ``sys.modules`` under ``magic``, it is what the guesser imports, so the guesser's own
    logic runs where libmagic is not installed. It records each call, which shows the guesser
    asks for a MIME type rather than a description. Carries its own contract test.
    """

    MagicException: ClassVar[type[Exception]] = FakeMagicError

    def __init__(self, answer: str | Exception) -> None:
        super().__init__("magic")
        self.answer: str | Exception = answer
        self.calls: list[tuple[str, bool]] = []

    def from_file(self, filename: str, mime: bool = False) -> str:
        self.calls.append((filename, mime))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer
