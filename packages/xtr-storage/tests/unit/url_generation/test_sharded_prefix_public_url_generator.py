from __future__ import annotations

import zlib

import pytest

from xtr_storage.config import Config
from xtr_storage.exception import InvalidArgumentError
from xtr_storage.url_generation.sharded_prefix_public_url_generator import (
    ShardedPrefixPublicUrlGenerator,
)


@pytest.mark.anyio
async def test_it_sends_a_path_to_the_prefix_its_hash_selects() -> None:
    prefixes = ["https://a/", "https://b/", "https://c/"]
    generator = ShardedPrefixPublicUrlGenerator(prefixes)

    path = "photos/logo.png"
    index = zlib.crc32(path.encode()) % len(prefixes)

    assert await generator.public_url(path, Config()) == prefixes[index] + path


@pytest.mark.anyio
async def test_the_same_path_always_resolves_to_the_same_prefix() -> None:
    generator = ShardedPrefixPublicUrlGenerator(["https://a/", "https://b/", "https://c/"])

    first = await generator.public_url("a/b.txt", Config())
    second = await generator.public_url("a/b.txt", Config())

    assert first == second


@pytest.mark.anyio
async def test_different_paths_spread_across_the_prefixes() -> None:
    prefixes = ["https://a/", "https://b/"]
    generator = ShardedPrefixPublicUrlGenerator(prefixes)

    # Two paths whose crc32 lands on different prefixes, computed here with the
    # same hash the generator uses, so the split is a fact rather than a hope.
    to_first = "photos/logo.png"
    to_second = "beta.txt"

    assert zlib.crc32(to_first.encode()) % len(prefixes) == 0
    assert zlib.crc32(to_second.encode()) % len(prefixes) == 1
    assert await generator.public_url(to_first, Config()) == "https://a/photos/logo.png"
    assert await generator.public_url(to_second, Config()) == "https://b/beta.txt"


def test_an_empty_run_of_prefixes_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = ShardedPrefixPublicUrlGenerator([])


@pytest.mark.anyio
async def test_it_escapes_characters_a_url_would_misread() -> None:
    prefixes = ["https://a/", "https://b/", "https://c/"]
    generator = ShardedPrefixPublicUrlGenerator(prefixes)
    path = "a b?c#d.txt"
    index = zlib.crc32(path.encode()) % len(prefixes)

    url = await generator.public_url(path, Config())

    assert url == prefixes[index] + "a%20b%3Fc%23d.txt"
