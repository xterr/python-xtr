"""Guessers answering one fixed MIME type, whatever the file holds."""

from __future__ import annotations

from typing import ClassVar, Final, final

from typing_extensions import override

from xtr_mime import MimeTypeGuesserInterface

__all__ = [
    "CONTAINER_BUILT_ANSWER",
    "AnsweringGuesser",
    "ContainerBuiltGuesser",
    "CountingGuesser",
    "LookalikeGuesser",
]

CONTAINER_BUILT_ANSWER: Final = "application/x-container-built"


@final
class AnsweringGuesser(MimeTypeGuesserInterface):
    """Answers ``answer`` for every file; ``None`` answers nothing."""

    def __init__(self, answer: str | None) -> None:
        self.answer = answer

    @override
    def is_guesser_supported(self) -> bool:
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return self.answer


@final
class ContainerBuiltGuesser(MimeTypeGuesserInterface):
    """A guesser the container builds from its class, answering :data:`CONTAINER_BUILT_ANSWER`."""

    @override
    def is_guesser_supported(self) -> bool:
        return True

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return CONTAINER_BUILT_ANSWER


@final
class LookalikeGuesser:
    """Has a guesser's methods without subclassing the interface."""

    def is_guesser_supported(self) -> bool:
        return True

    def guess_mime_type(self, path: str) -> str | None:
        return CONTAINER_BUILT_ANSWER if path else None


@final
class CountingGuesser(MimeTypeGuesserInterface):
    """Counts how many the container builds — built only when the table holding it is."""

    built: ClassVar[int] = 0

    def __init__(self) -> None:
        CountingGuesser.built += 1

    @override
    def is_guesser_supported(self) -> bool:
        return False

    @override
    def guess_mime_type(self, path: str) -> str | None:
        return None if path else CONTAINER_BUILT_ANSWER
