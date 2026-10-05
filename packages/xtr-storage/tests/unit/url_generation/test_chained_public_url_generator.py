from __future__ import annotations

from typing import final

import pytest

from xtr_storage.config import Config
from xtr_storage.exception import UnableToGeneratePublicUrlError
from xtr_storage.url_generation.chained_public_url_generator import ChainedPublicUrlGenerator


@final
class RecordingGenerator:
    """A generator that answers with a fixed url and remembers what it was asked."""

    def __init__(self, url: str) -> None:
        self._url = url
        self.paths: list[str] = []

    async def public_url(self, path: str, config: Config) -> str:
        del config
        self.paths.append(path)

        return self._url


@final
class DecliningGenerator:
    """A generator that always declines, the way one with no address for a file does."""

    def __init__(self) -> None:
        self.calls = 0

    async def public_url(self, path: str, config: Config) -> str:
        del config
        self.calls += 1

        raise UnableToGeneratePublicUrlError(path, "declined")


@pytest.mark.anyio
async def test_it_returns_the_first_address_a_generator_gives() -> None:
    declining = DecliningGenerator()
    answering = RecordingGenerator("https://a/x")
    generator = ChainedPublicUrlGenerator([declining, answering])

    assert await generator.public_url("x", Config()) == "https://a/x"
    assert declining.calls == 1
    assert answering.paths == ["x"]


@pytest.mark.anyio
async def test_it_stops_at_the_first_generator_that_answers() -> None:
    first = RecordingGenerator("https://a/x")
    second = RecordingGenerator("https://b/x")
    generator = ChainedPublicUrlGenerator([first, second])

    assert await generator.public_url("x", Config()) == "https://a/x"
    assert second.paths == []


@pytest.mark.anyio
async def test_it_declines_once_every_generator_has_declined() -> None:
    generator = ChainedPublicUrlGenerator([DecliningGenerator(), DecliningGenerator()])

    with pytest.raises(UnableToGeneratePublicUrlError):
        _ = await generator.public_url("x", Config())


@pytest.mark.anyio
async def test_an_empty_chain_declines() -> None:
    generator = ChainedPublicUrlGenerator([])

    with pytest.raises(UnableToGeneratePublicUrlError):
        _ = await generator.public_url("x", Config())
