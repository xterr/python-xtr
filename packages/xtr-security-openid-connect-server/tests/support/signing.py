"""Real signers over freshly minted keys, for the ID-token tests.

Nothing here is a double: each key is minted by the signing library the
authorization server signs with, the tokens are signed by the provider its
bundle wires, and the key id is the one the published key set names the key
by. A test can therefore decode the ID token an answer carries and assert on
what it says, rather than assert that a mock was called.

One key is minted per algorithm the tests sign with, once, when this module is
imported: minting an RSA key costs far more than every test using it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

from xtr_clock import MockClock
from xtr_security_jwt.services.jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.key_loader import (
    RawKeyLoader,
    generate_signing_key,
    signing_key_id,
)
from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner

if TYPE_CHECKING:
    from joserfc.jwk import ECKey, OKPKey, RSAKey
    from xtr_clock import ClockInterface

__all__ = [
    "ALGORITHMS",
    "FROZEN_NOW",
    "ISSUER",
    "make_clock",
    "make_signer",
    "signing_key",
]

#: The signature algorithms the tests sign with: one RSA, one elliptic-curve.
ALGORITHMS: Final[tuple[str, ...]] = ("RS256", "ES256")

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


def signing_key(algorithm: str) -> RSAKey | ECKey | OKPKey:
    """Return the key minted for ``algorithm``, which verifies what it signed."""
    return _KEYS[algorithm]


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
