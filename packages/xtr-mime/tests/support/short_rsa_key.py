"""A 512-bit RSA key, too short for any signer: cryptography generates none, but loads one."""

from __future__ import annotations

from typing import Final

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

__all__ = ["short_rsa_pem"]

# Two 256-bit primes.
_SHORT_P: Final = 0xDC7EB2550C06E85F6483E44589A869502F426C247CB40F4814147537F5C24A43
_SHORT_Q: Final = 0xAA04557F88DC584618E28166050BB41320C9F3C7569769BDE1BD52D1ED363631


def short_rsa_pem() -> bytes:
    """Return the 512-bit RSA key as PKCS#8 PEM."""
    p, q, e = _SHORT_P, _SHORT_Q, 65537
    d = pow(e, -1, (p - 1) * (q - 1))
    numbers = rsa.RSAPrivateNumbers(
        p,
        q,
        d,
        rsa.rsa_crt_dmp1(d, p),
        rsa.rsa_crt_dmq1(d, q),
        rsa.rsa_crt_iqmp(p, q),
        rsa.RSAPublicNumbers(e, p * q),
    )
    return numbers.private_key().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
