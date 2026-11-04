"""The pass hands the table every guesser tagged for it, the highest priority asked first."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from xtr_dependency_injection.exception import ServiceResolutionError

from tests.support.answering_guessers import (
    CONTAINER_BUILT_ANSWER,
    AnsweringGuesser,
    ContainerBuiltGuesser,
    LookalikeGuesser,
)
from tests.support.mime_kernel import Registration, mime_kernel
from xtr_mime import MimeTypesInterface
from xtr_mime.bundle import MIME_TYPE_GUESSER_TAG
from xtr_mime.exception import LogicError

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@pytest.fixture
def unnamed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A file whose name the table knows nothing about, and no libmagic to sniff it.

    The table's own libmagic guesser would answer for the file where libmagic is installed;
    leaving it unable to run keeps every answer here the tagged guessers' alone.
    """
    monkeypatch.setitem(sys.modules, "magic", None)
    path = tmp_path / "unnamed"
    _ = path.write_bytes(b"\x00")
    return str(path)


async def guess(unnamed: str, *registrations: Registration) -> str | None:
    async with await mime_kernel(None, *registrations).boot() as booted:
        table = await booted.container.get(MimeTypesInterface)
    return table.guess_mime_type(unnamed)


async def test_a_tagged_guesser_is_registered(unnamed: str) -> None:
    tagged = Registration(AnsweringGuesser("image/x-tagged"), tag=MIME_TYPE_GUESSER_TAG)

    assert await guess(unnamed, tagged) == "image/x-tagged"


async def test_no_guesser_leaves_the_table_answering_alone(unnamed: str) -> None:
    assert await guess(unnamed) is None


async def test_the_highest_priority_is_asked_first(unnamed: str) -> None:
    low = Registration(
        AnsweringGuesser("image/x-low"), "low", MIME_TYPE_GUESSER_TAG, {"priority": -5}
    )
    high = Registration(
        AnsweringGuesser("image/x-high"), "high", MIME_TYPE_GUESSER_TAG, {"priority": 5}
    )

    assert await guess(unnamed, low, high) == "image/x-high"


async def test_among_equal_priorities_the_first_registered_is_asked_first(unnamed: str) -> None:
    first = Registration(AnsweringGuesser("image/x-first"), "first", MIME_TYPE_GUESSER_TAG)
    second = Registration(AnsweringGuesser("image/x-second"), "second", MIME_TYPE_GUESSER_TAG)

    assert await guess(unnamed, first, second) == "image/x-first"


async def test_the_definition_priority_applies_without_a_tag_priority(unnamed: str) -> None:
    first = Registration(AnsweringGuesser("image/x-first"), "first", MIME_TYPE_GUESSER_TAG)
    second = Registration(
        AnsweringGuesser("image/x-second"), "second", MIME_TYPE_GUESSER_TAG, priority=1
    )

    assert await guess(unnamed, first, second) == "image/x-second"


async def test_a_guesser_answering_nothing_passes_to_the_next(unnamed: str) -> None:
    silent = Registration(AnsweringGuesser(None), "silent", MIME_TYPE_GUESSER_TAG, {"priority": 1})
    answering = Registration(AnsweringGuesser("image/x-next"), "next", MIME_TYPE_GUESSER_TAG)

    assert await guess(unnamed, silent, answering) == "image/x-next"


async def test_a_class_subclassing_the_interface_is_tagged_without_being_told(
    unnamed: str,
) -> None:
    assert await guess(unnamed, Registration(ContainerBuiltGuesser)) == CONTAINER_BUILT_ANSWER


async def test_an_explicit_priority_wins_over_the_tag_autoconfiguration_adds(
    unnamed: str,
) -> None:
    built = Registration(
        ContainerBuiltGuesser, tag=MIME_TYPE_GUESSER_TAG, attributes={"priority": -1}
    )
    plain = Registration(AnsweringGuesser("image/x-plain"), "plain", MIME_TYPE_GUESSER_TAG)

    assert await guess(unnamed, built, plain) == "image/x-plain"


async def test_a_class_with_only_the_methods_is_not_tagged(unnamed: str) -> None:
    assert await guess(unnamed, Registration(LookalikeGuesser)) is None


async def test_a_class_with_only_the_methods_is_asked_once_tagged(unnamed: str) -> None:
    tagged = Registration(LookalikeGuesser, tag=MIME_TYPE_GUESSER_TAG)

    assert await guess(unnamed, tagged) == CONTAINER_BUILT_ANSWER


async def test_a_tagged_service_that_is_not_a_guesser_fails_the_table() -> None:
    tagged = Registration(object(), tag=MIME_TYPE_GUESSER_TAG)

    async with await mime_kernel(None, tagged).boot() as booted:
        with pytest.raises(ServiceResolutionError) as raised:
            _ = await booted.container.get(MimeTypesInterface)

    assert isinstance(raised.value.__cause__, LogicError)
    assert "is not a guesser" in str(raised.value.__cause__)


async def test_a_priority_that_is_not_an_integer_fails_the_build() -> None:
    tagged = Registration(
        AnsweringGuesser("image/x"), tag=MIME_TYPE_GUESSER_TAG, attributes={"priority": "1"}
    )

    with pytest.raises(LogicError, match="priority that is not an integer"):
        _ = await mime_kernel(None, tagged).boot()
