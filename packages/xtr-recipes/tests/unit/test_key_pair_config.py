from __future__ import annotations

from xtr_recipes.key_pair_config import KEY_ALGORITHMS, KeyPairConfig


def test_a_key_is_unencrypted_unless_a_passphrase_is_named() -> None:
    assert KeyPairConfig("RS256").passphrase is None


def test_no_shared_secret_algorithm_is_minted() -> None:
    assert not any(algorithm.startswith("HS") for algorithm in KEY_ALGORITHMS)
