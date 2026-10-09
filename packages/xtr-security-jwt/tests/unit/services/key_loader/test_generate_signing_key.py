"""The signing-key generator mints the key material an algorithm demands."""

from __future__ import annotations

from base64 import urlsafe_b64decode

import pytest
from joserfc.jwk import ECKey, OKPKey, RSAKey
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_jwt.services.key_loader.generate_signing_key import (
    RSA_KEY_SIZE,
    generate_signing_key,
)


def _modulus_bits(key: RSAKey) -> int:
    """Return the bit length of the modulus ``key`` publishes as its ``n`` member."""
    modulus = key.as_dict(private=False)["n"]
    assert isinstance(modulus, str)
    return len(urlsafe_b64decode(modulus + "=" * (-len(modulus) % 4))) * 8


@pytest.mark.parametrize(
    "algorithm",
    ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"],
)
def test_an_rsa_algorithm_gets_a_private_rsa_key(algorithm: str) -> None:
    key = generate_signing_key(algorithm)

    assert isinstance(key, RSAKey)
    assert key.is_private


def test_a_minted_rsa_key_carries_the_modulus_the_library_pins() -> None:
    key = generate_signing_key("RS256")

    assert isinstance(key, RSAKey)
    assert _modulus_bits(key) == RSA_KEY_SIZE


def test_an_elliptic_curve_algorithm_gets_a_private_ec_key() -> None:
    key = generate_signing_key("ES256")

    assert isinstance(key, ECKey)
    assert key.is_private


def test_the_edwards_algorithm_gets_a_private_okp_key() -> None:
    key = generate_signing_key("EdDSA")

    assert isinstance(key, OKPKey)
    assert key.is_private


@pytest.mark.parametrize(
    ("algorithm", "curve"),
    [
        ("ES256", "P-256"),
        ("ES384", "P-384"),
        ("ES512", "P-521"),
        ("EdDSA", "Ed25519"),
    ],
)
def test_a_curve_key_sits_on_the_curve_its_algorithm_names(algorithm: str, curve: str) -> None:
    key = generate_signing_key(algorithm)

    assert key.as_dict(private=False)["crv"] == curve


def test_a_minted_key_carries_the_id_it_is_given() -> None:
    key = generate_signing_key("RS256", "chosen")

    assert key.kid == "chosen"


def test_a_minted_key_given_no_id_carries_none() -> None:
    key = generate_signing_key("RS256")

    assert key.kid is None


def test_a_shared_secret_algorithm_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="HS256"):
        _ = generate_signing_key("HS256")


def test_an_algorithm_this_library_does_not_sign_with_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = generate_signing_key("none")
