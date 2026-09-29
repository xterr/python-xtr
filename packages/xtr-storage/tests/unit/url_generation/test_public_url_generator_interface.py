from __future__ import annotations

import pytest

from xtr_storage.config import Config
from xtr_storage.exception import UnableToGeneratePublicUrlError
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface


class FakePublicUrlGenerator:
    """Addresses whatever is under one host, and refuses to address a directory."""

    async def public_url(self, path: str, config: Config) -> str:
        del config

        if path.endswith("/"):
            raise UnableToGeneratePublicUrlError(path, "a directory has no address")

        return f"https://files.example/{path}"


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakePublicUrlGenerator(), PublicUrlGeneratorInterface)


def test_an_object_without_the_method_does_not_satisfy_the_interface() -> None:
    class WithoutPublicUrl:
        pass

    assert not isinstance(WithoutPublicUrl(), PublicUrlGeneratorInterface)


@pytest.mark.anyio
async def test_a_generator_addresses_a_file_through_the_interface() -> None:
    generator: PublicUrlGeneratorInterface = FakePublicUrlGenerator()

    assert await generator.public_url("a.txt", Config()) == "https://files.example/a.txt"


@pytest.mark.anyio
async def test_a_generator_refuses_what_it_cannot_address() -> None:
    generator: PublicUrlGeneratorInterface = FakePublicUrlGenerator()

    with pytest.raises(UnableToGeneratePublicUrlError):
        _ = await generator.public_url("photos/", Config())
