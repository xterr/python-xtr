"""Signing keys built once for the whole suite, and helpers around them."""

from __future__ import annotations

from joserfc.jwk import ECKey, OctKey, RSAKey

__all__ = [
    "EC_PRIVATE_PEM",
    "EC_PUBLIC_PEM",
    "HMAC_SECRET",
    "RSA_PRIVATE_PEM",
    "RSA_PUBLIC_PEM",
    "SECOND_RSA_PRIVATE_PEM",
    "SECOND_RSA_PUBLIC_PEM",
]

_RSA = RSAKey.generate_key(2048, parameters={"kid": "rsa-1"})
RSA_PRIVATE_PEM: str = _RSA.as_pem(private=True).decode("utf-8")
RSA_PUBLIC_PEM: str = _RSA.as_pem(private=False).decode("utf-8")

_SECOND_RSA = RSAKey.generate_key(2048, parameters={"kid": "rsa-2"})
SECOND_RSA_PRIVATE_PEM: str = _SECOND_RSA.as_pem(private=True).decode("utf-8")
SECOND_RSA_PUBLIC_PEM: str = _SECOND_RSA.as_pem(private=False).decode("utf-8")

_EC = ECKey.generate_key("P-256", parameters={"kid": "ec-1"})
EC_PRIVATE_PEM: str = _EC.as_pem(private=True).decode("utf-8")
EC_PUBLIC_PEM: str = _EC.as_pem(private=False).decode("utf-8")

_SECRET_VALUE = OctKey.generate_key(256, parameters={"kid": "hs-1"}).as_dict()["k"]
HMAC_SECRET: str = _SECRET_VALUE if isinstance(_SECRET_VALUE, str) else "".join(_SECRET_VALUE)
