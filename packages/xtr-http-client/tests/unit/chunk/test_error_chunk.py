from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_http_client_contracts import ChunkInterface

from xtr_http_client.chunk import ErrorChunk
from xtr_http_client.exception import TransportError, TransportTimeoutError

if TYPE_CHECKING:
    from collections.abc import Callable

IDLE = 'Idle timeout reached for "https://example.com/".'
BROKEN = OSError("Connection reset by peer")

EVERY_OTHER_QUESTION: list[Callable[[ErrorChunk], object]] = [
    lambda chunk: chunk.is_first(),
    lambda chunk: chunk.is_last(),
    lambda chunk: chunk.get_informational_status(),
    lambda chunk: chunk.get_content(),
]


def test_it_is_a_chunk() -> None:
    chunk: ChunkInterface = ErrorChunk(0, IDLE)
    assert isinstance(chunk, ChunkInterface)


def test_a_timeout_chunk_says_so_without_raising() -> None:
    chunk = ErrorChunk(7, IDLE)
    assert chunk.is_timeout() is True


def test_a_failed_transfer_raises_when_asked_whether_it_timed_out() -> None:
    chunk = ErrorChunk(7, BROKEN)
    with pytest.raises(TransportError, match="Connection reset by peer") as raised:
        _ = chunk.is_timeout()
    assert raised.value.__cause__ is BROKEN
    assert not isinstance(raised.value, TransportTimeoutError)


@pytest.mark.parametrize("ask", EVERY_OTHER_QUESTION)
def test_every_other_question_about_a_timeout_raises_a_timeout(
    ask: Callable[[ErrorChunk], object],
) -> None:
    chunk = ErrorChunk(0, IDLE)
    with pytest.raises(TransportTimeoutError, match="Idle timeout reached"):
        _ = ask(chunk)


@pytest.mark.parametrize("ask", EVERY_OTHER_QUESTION)
def test_every_other_question_about_a_failure_raises_with_the_original_cause(
    ask: Callable[[ErrorChunk], object],
) -> None:
    chunk = ErrorChunk(0, BROKEN)
    with pytest.raises(TransportError) as raised:
        _ = ask(chunk)
    assert str(raised.value) == "Connection reset by peer"
    assert raised.value.__cause__ is BROKEN


def test_the_offset_and_the_error_never_raise() -> None:
    chunk = ErrorChunk(99, BROKEN)
    assert chunk.get_offset() == 99
    assert chunk.get_error() == "Connection reset by peer"


def test_it_starts_out_not_having_reported_anything() -> None:
    assert ErrorChunk(0, IDLE).did_throw() is False


def test_it_remembers_that_a_reader_was_told() -> None:
    chunk = ErrorChunk(0, IDLE)
    with pytest.raises(TransportTimeoutError):
        _ = chunk.is_last()
    assert chunk.did_throw() is True


def test_a_timeout_answered_without_raising_still_counts_as_telling_the_reader() -> None:
    chunk = ErrorChunk(0, IDLE)
    assert chunk.is_timeout() is True
    assert chunk.did_throw() is True


def test_it_records_how_long_the_transfer_was_allowed_to_stay_quiet() -> None:
    assert ErrorChunk(0, IDLE, 12.5).timeout == 12.5
    assert ErrorChunk(0, IDLE).timeout == 0.0
