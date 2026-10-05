from __future__ import annotations

from datetime import UTC, datetime

import pytest

from xtr_storage.config import Config
from xtr_storage.exception import UnableToGenerateTemporaryUrlError
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)


class FakeTemporaryUrlGenerator:
    """Signs an address for one file, and has nothing to sign a directory with."""

    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        del config

        if path.endswith("/"):
            raise UnableToGenerateTemporaryUrlError(path, "a directory cannot be signed")

        return f"https://files.example/{path}?until={int(expires_at.timestamp())}"


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeTemporaryUrlGenerator(), TemporaryUrlGeneratorInterface)


def test_an_object_without_the_method_does_not_satisfy_the_interface() -> None:
    class WithoutTemporaryUrl:
        pass

    assert not isinstance(WithoutTemporaryUrl(), TemporaryUrlGeneratorInterface)


@pytest.mark.anyio
async def test_a_generator_signs_an_address_through_the_interface() -> None:
    generator: TemporaryUrlGeneratorInterface = FakeTemporaryUrlGenerator()
    expires_at = datetime(2030, 1, 1, tzinfo=UTC)

    signed = await generator.temporary_url("a.txt", expires_at, Config())

    assert signed == f"https://files.example/a.txt?until={int(expires_at.timestamp())}"


@pytest.mark.anyio
async def test_a_generator_refuses_what_it_cannot_sign() -> None:
    generator: TemporaryUrlGeneratorInterface = FakeTemporaryUrlGenerator()

    with pytest.raises(UnableToGenerateTemporaryUrlError):
        _ = await generator.temporary_url("photos/", datetime(2030, 1, 1, tzinfo=UTC), Config())
