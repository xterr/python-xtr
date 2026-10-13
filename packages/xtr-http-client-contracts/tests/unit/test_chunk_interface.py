from __future__ import annotations

from tests.support.fake_chunk import FakeChunk
from xtr_http_client_contracts import ChunkInterface


def test_a_chunk_answering_every_question_satisfies_it() -> None:
    chunk: ChunkInterface = FakeChunk()

    assert isinstance(chunk, ChunkInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), ChunkInterface)
