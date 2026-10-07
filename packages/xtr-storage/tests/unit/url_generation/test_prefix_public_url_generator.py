from __future__ import annotations

import pytest

from xtr_storage.config import Config
from xtr_storage.url_generation.prefix_public_url_generator import PrefixPublicUrlGenerator


@pytest.mark.anyio
async def test_it_joins_a_path_to_the_prefix() -> None:
    generator = PrefixPublicUrlGenerator("https://cdn/x/")

    assert await generator.public_url("a/b.txt", Config()) == "https://cdn/x/a/b.txt"


@pytest.mark.anyio
async def test_it_puts_exactly_one_separator_between_prefix_and_path() -> None:
    trailing = PrefixPublicUrlGenerator("https://cdn/x/")
    bare = PrefixPublicUrlGenerator("https://cdn/x")

    assert await trailing.public_url("a/b.txt", Config()) == "https://cdn/x/a/b.txt"
    assert await bare.public_url("a/b.txt", Config()) == "https://cdn/x/a/b.txt"


@pytest.mark.anyio
async def test_it_drops_a_leading_separator_the_path_carries() -> None:
    generator = PrefixPublicUrlGenerator("https://cdn/x/")

    assert await generator.public_url("/a/b.txt", Config()) == "https://cdn/x/a/b.txt"


@pytest.mark.anyio
async def test_an_empty_prefix_is_a_transparent_pass_through() -> None:
    generator = PrefixPublicUrlGenerator("")

    assert await generator.public_url("a/b.txt", Config()) == "a/b.txt"


@pytest.mark.anyio
async def test_it_escapes_characters_a_url_would_misread() -> None:
    generator = PrefixPublicUrlGenerator("https://cdn/x/")

    url = await generator.public_url("a b?c#d.txt", Config())

    assert url == "https://cdn/x/a%20b%3Fc%23d.txt"


@pytest.mark.anyio
async def test_it_keeps_the_separators_that_structure_the_path() -> None:
    generator = PrefixPublicUrlGenerator("https://cdn/x/")

    assert (
        await generator.public_url("one/two/c d.txt", Config()) == "https://cdn/x/one/two/c%20d.txt"
    )
