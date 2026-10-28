from __future__ import annotations

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from xtr_recipes.key_minting import RSA_KEY_SIZE, mint_private_key


def test_an_rsa_key_has_the_minted_size() -> None:
    key = load_pem_private_key(mint_private_key("RS256", None).encode(), None)

    assert isinstance(key, rsa.RSAPrivateKey)
    assert key.key_size == RSA_KEY_SIZE


@pytest.mark.parametrize(("algorithm", "curve"), [("ES256", "secp256r1"), ("ES512", "secp521r1")])
def test_an_elliptic_curve_key_is_on_the_algorithms_curve(algorithm: str, curve: str) -> None:
    key = load_pem_private_key(mint_private_key(algorithm, None).encode(), None)

    assert isinstance(key, ec.EllipticCurvePrivateKey)
    assert key.curve.name == curve


def test_an_eddsa_key_is_ed25519() -> None:
    key = load_pem_private_key(mint_private_key("EdDSA", None).encode(), None)

    assert isinstance(key, ed25519.Ed25519PrivateKey)


def test_a_key_given_a_passphrase_only_opens_with_it() -> None:
    pem = mint_private_key("ES256", "secret").encode()

    assert isinstance(load_pem_private_key(pem, b"secret"), ec.EllipticCurvePrivateKey)
    with pytest.raises(TypeError):
        _ = load_pem_private_key(pem, None)


def test_an_empty_passphrase_writes_an_unencrypted_key() -> None:
    assert b"ENCRYPTED" not in mint_private_key("ES256", "").encode()
