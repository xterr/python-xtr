"""Real signers over freshly minted keys, for the ID-token tests.

Nothing here is a double: each key is minted by the signing library the
authorization server signs with, the tokens are signed by the provider its
bundle wires, and the key id is the one the published key set names the key
by. A test can therefore decode the ID token an answer carries and assert on
what it says, rather than assert that a mock was called.

One key is minted per algorithm the tests sign with, once, when this module is
imported: minting an RSA key costs far more than every test using it. ``EdDSA``
gets one per curve, because its name does not say which curve its key is on.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from joserfc.jwk import OKPKey
from xtr_clock import MockClock
from xtr_security_jwt.services.jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader import (
    RawKeyLoader,
    generate_signing_key,
    signing_key_id,
)
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner

if TYPE_CHECKING:
    from joserfc.jwk import ECKey, RSAKey
    from xtr_clock import ClockInterface

__all__ = [
    "ALGORITHMS",
    "EDDSA_DEPRECATION",
    "FROZEN_NOW",
    "ISSUER",
    "edwards_key",
    "make_clock",
    "make_edwards_signer",
    "make_signer",
    "signing_key",
]

#: The signature algorithms the tests sign with: one RSA, one elliptic-curve.
ALGORITHMS: Final[tuple[str, ...]] = ("RS256", "ES256")

#: What a test signing or verifying with ``EdDSA`` ignores. The signing library
#: warns on every use of that name, which RFC 9864 deprecates for names saying
#: the curve too; ``EdDSA`` is still the one this server's keys sign under.
EDDSA_DEPRECATION: Final[str] = "ignore:EdDSA is deprecated:joserfc.errors.SecurityWarning"

#: The issuer the tokens claim, an origin with no path.
ISSUER: Final[str] = "https://authorization.example.com"

#: Where the frozen clock stands, so ``iat`` and ``exp`` are exact.
FROZEN_NOW: Final[datetime] = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)

_KEYS: Final[dict[str, RSAKey | ECKey | OKPKey]] = {
    algorithm: generate_signing_key(algorithm) for algorithm in ALGORITHMS
}

_LOADERS: Final[dict[str, RawKeyLoader]] = {
    algorithm: RawKeyLoader(key.as_pem(private=True).decode("utf-8"), None)
    for algorithm, key in _KEYS.items()
}

#: An ``EdDSA`` key on each curve: Ed25519, the one the server mints a key on,
#: and Ed448, which only a deployment bringing its own key signs over — and
#: whose ``at_hash`` digest is not the one the algorithm's name suggests.
_EDWARDS_KEYS: Final[dict[str, OKPKey]] = {
    "Ed25519": OKPKey.generate_key("Ed25519"),
    "Ed448": OKPKey.generate_key("Ed448"),
}


def signing_key(algorithm: str) -> RSAKey | ECKey | OKPKey:
    """Return the key minted for ``algorithm``, which verifies what it signed."""
    return _KEYS[algorithm]


def edwards_key(curve: str) -> OKPKey:
    """Return the ``EdDSA`` key minted on ``curve``, which verifies what it signed."""
    return _EDWARDS_KEYS[curve]


def make_clock(now: datetime = FROZEN_NOW) -> MockClock:
    """Return a clock frozen at ``now``."""
    return MockClock(now)


def make_signer(
    algorithm: str,
    audience: str | None = None,
    clock: ClockInterface | None = None,
) -> AccessTokenSigner:
    """Return a signer over the key minted for ``algorithm``, frozen unless a clock is given."""
    reading = clock if clock is not None else make_clock()
    loader = _LOADERS[algorithm]
    return AccessTokenSigner(
        jws_provider=JoserfcJwsProvider(loader, algorithm, None, 0, reading),
        key_id=signing_key_id(loader, algorithm),
        issuer=ISSUER,
        clock=reading,
        audience=audience,
    )


def make_edwards_signer(curve: str) -> AccessTokenSigner:
    """Return an ``EdDSA`` signer over the key minted on ``curve``, frozen."""
    clock = make_clock()
    loader = RawKeyLoader(edwards_key(curve).as_pem(private=True).decode("utf-8"), None)
    return AccessTokenSigner(
        jws_provider=JoserfcJwsProvider(loader, "EdDSA", None, 0, clock),
        key_id=signing_key_id(loader, "EdDSA"),
        issuer=ISSUER,
        clock=clock,
    )
