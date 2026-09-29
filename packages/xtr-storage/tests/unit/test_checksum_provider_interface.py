from __future__ import annotations

import pytest

from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import ChecksumAlgorithmNotSupportedError


class FakeChecksumProvider:
    """A backend that keeps one digest of its own and refuses the rest."""

    async def checksum(self, path: str, config: Config) -> str:
        algorithm = config.str_option(Config.CHECKSUM_ALGORITHM, "md5")

        if algorithm != "etag":
            raise ChecksumAlgorithmNotSupportedError(path, algorithm)

        return f"etag-of-{path}"


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeChecksumProvider(), ChecksumProviderInterface)


def test_an_adapter_without_the_method_does_not_satisfy_the_interface() -> None:
    class WithoutChecksum:
        pass

    assert not isinstance(WithoutChecksum(), ChecksumProviderInterface)


@pytest.mark.anyio
async def test_a_provider_answers_for_the_algorithm_it_keeps() -> None:
    provider: ChecksumProviderInterface = FakeChecksumProvider()

    assert await provider.checksum("a.txt", Config({Config.CHECKSUM_ALGORITHM: "etag"})) == (
        "etag-of-a.txt"
    )


@pytest.mark.anyio
async def test_a_provider_refuses_an_algorithm_it_does_not_keep() -> None:
    provider: ChecksumProviderInterface = FakeChecksumProvider()

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await provider.checksum("a.txt", Config())
