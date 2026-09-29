from __future__ import annotations

from xtr_storage.path.path_normalizer_interface import PathNormalizerInterface
from xtr_storage.path.whitespace_path_normalizer import WhitespacePathNormalizer


def test_the_whitespace_normalizer_satisfies_the_interface() -> None:
    assert isinstance(WhitespacePathNormalizer(), PathNormalizerInterface)


def test_an_object_missing_the_method_does_not_satisfy_the_interface() -> None:
    class WithoutNormalize:
        pass

    assert not isinstance(WithoutNormalize(), PathNormalizerInterface)


def test_a_structural_match_satisfies_the_interface() -> None:
    class FixedNormalizer:
        def normalize_path(self, path: str) -> str:
            del path
            return ""

    assert isinstance(FixedNormalizer(), PathNormalizerInterface)
