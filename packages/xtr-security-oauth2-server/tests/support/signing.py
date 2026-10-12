"""A real signer over a freshly minted key, for the access-token tests.

Nothing here is a double: the key is minted by the signing library this
package depends on, the token is signed by the provider the bundle wires, and
the key id is the one the published key set would name it by. A test can
therefore decode what an entity produced and assert on it, rather than assert
that a mock was called.

The key pair is minted once, when this module is imported: minting an RSA key
costs far more than every test using it put together.
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
    from joserfc.jwk import Key
    from xtr_clock import ClockInterface

#: The signature algorithm every test here signs and verifies with.
ALGORITHM: Final[str] = "RS256"

#: The issuer the tokens claim, an origin with no path.
ISSUER: Final[str] = "https://authorization.example.com"

#: Where the frozen clock stands, so ``iat``, ``nbf`` and ``exp`` are exact.
FROZEN_NOW: Final[datetime] = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)

SIGNING_KEY: Final[Key] = generate_signing_key(ALGORITHM)

#: The minted key as the PEM a deployment would mount, so a test application
#: can configure one without minting a second.
SIGNING_KEY_PEM: Final[str] = SIGNING_KEY.as_pem(private=True).decode("utf-8")

KEY_LOADER: Final[RawKeyLoader] = RawKeyLoader(SIGNING_KEY_PEM, None)
"""The loader over the minted key, which is what publishes the key set too."""

#: The id the signing key is published under, and the one a token's ``kid`` names.
KEY_ID: Final[str] = signing_key_id(KEY_LOADER, ALGORITHM)


def make_clock(now: datetime = FROZEN_NOW) -> MockClock:
    """Return a clock frozen at ``now``."""
    return MockClock(now)


def make_signer(
    audience: str | None = None,
    clock: ClockInterface | None = None,
) -> AccessTokenSigner:
    """Return a signer over the minted key, frozen unless a clock is given."""
    reading = clock if clock is not None else make_clock()
    return AccessTokenSigner(
        jws_provider=JoserfcJwsProvider(KEY_LOADER, ALGORITHM, None, 0, reading),
        key_id=KEY_ID,
        issuer=ISSUER,
        clock=reading,
        audience=audience,
    )
