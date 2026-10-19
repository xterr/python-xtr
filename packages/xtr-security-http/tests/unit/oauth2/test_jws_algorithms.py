"""The JWS algorithm map an OAuth2 client signs with."""

from __future__ import annotations

import pytest
from joserfc.jwk import ECKey, OctKey, RSAKey
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.oauth2 import JwsAlgorithms


def test_the_asymmetric_map_names_each_algorithms_key_type() -> None:
    assert set(JwsAlgorithms.ASYMMETRIC) == {
        "RS256",
        "RS384",
        "RS512",
        "ES256",
        "ES384",
        "ES512",
        "PS256",
        "PS384",
        "PS512",
    }
    assert set(JwsAlgorithms.ASYMMETRIC.values()) == {"RSA", "EC"}


def test_the_mac_map_names_each_algorithms_key_type() -> None:
    assert set(JwsAlgorithms.MAC) == {"HS256", "HS384", "HS512"}
    assert set(JwsAlgorithms.MAC.values()) == {"oct"}


def test_the_curves_map_names_the_curve_each_ecdsa_algorithm_signs_on() -> None:
    assert dict(JwsAlgorithms.CURVES) == {"ES256": "P-256", "ES384": "P-384", "ES512": "P-521"}


def test_check_key_accepts_an_rsa_key_for_an_rsa_algorithm() -> None:
    key = RSAKey.generate_key(2048)

    JwsAlgorithms.check_key(key, "RS256")


def test_check_key_accepts_an_ec_key_on_the_algorithms_curve() -> None:
    key = ECKey.generate_key("P-384")

    JwsAlgorithms.check_key(key, "ES384")


def test_check_key_accepts_an_oct_key_for_a_mac_algorithm() -> None:
    key = OctKey.import_key("a-shared-secret-of-thirty-two-bytes!")

    JwsAlgorithms.check_key(key, "HS256")


def test_check_key_refuses_a_key_of_the_wrong_type() -> None:
    shared_secret = OctKey.import_key("a-shared-secret-of-thirty-two-bytes!")

    with pytest.raises(InvalidArgumentError) as raised:
        JwsAlgorithms.check_key(shared_secret, "RS256")

    assert str(raised.value) == (
        'The "RS256" algorithm signs with a key of the "RSA" type, '
        'and the given JWK is of the "oct" type.'
    )


def test_check_key_refuses_a_shared_secret_for_an_asymmetric_algorithm() -> None:
    rsa_key = RSAKey.generate_key(2048)

    with pytest.raises(InvalidArgumentError) as raised:
        JwsAlgorithms.check_key(rsa_key, "HS256")

    assert str(raised.value) == (
        'The "HS256" algorithm signs with a key of the "oct" type, '
        'and the given JWK is of the "RSA" type.'
    )


def test_check_key_refuses_an_ec_key_on_another_curve() -> None:
    p_256 = ECKey.generate_key("P-256")

    with pytest.raises(InvalidArgumentError) as raised:
        JwsAlgorithms.check_key(p_256, "ES384")

    assert str(raised.value) == (
        'The "ES384" algorithm signs with a key on the "P-384" curve '
        '(RFC 7518, Section 3.4), and the given JWK is on the "P-256" curve.'
    )


def test_check_key_refuses_an_algorithm_the_suite_does_not_sign_with() -> None:
    key = RSAKey.generate_key(2048)

    with pytest.raises(InvalidArgumentError) as raised:
        JwsAlgorithms.check_key(key, "HS128")

    assert str(raised.value) == (
        '"HS128" is not a JWS algorithm an OAuth2 client signs with. '
        'Use one of "RS256", "RS384", "RS512", "ES256", "ES384", "ES512", '
        '"PS256", "PS384", "PS512", "HS256", "HS384", "HS512".'
    )
