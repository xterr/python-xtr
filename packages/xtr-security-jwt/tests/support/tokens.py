"""Mint tokens the served tests present, signed with the fixture key."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_clock import MockClock, SystemClock
from xtr_security_core.user.in_memory_user import InMemoryUser

from tests.support.fakes import RecordingDispatcher
from xtr_security_jwt.encoder.default_jwt_encoder import DefaultJwtEncoder
from xtr_security_jwt.services.jws_provider.joserfc_jws_provider import JoserfcJwsProvider
from xtr_security_jwt.services.jwt_manager import JwtManager
from xtr_security_jwt.services.key_loader.raw_key_loader import RawKeyLoader

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["mint_token"]


async def mint_token(
    private_pem: str,
    identifier: str,
    roles: Sequence[str] = ("ROLE_USER",),
    *,
    ttl: int = 3600,
    when: str | None = None,
    user_id_claim: str = "username",
) -> str:
    """Sign a token for ``identifier`` with ``roles`` using the fixture key.

    The token is stamped by the real clock by default, so it verifies against the
    served application's own clock; a frozen ``when`` mints a token dated then,
    for the expiry tests.
    """
    clock = MockClock(when) if when is not None else SystemClock()
    provider = JoserfcJwsProvider(RawKeyLoader(private_pem, None), "RS256", ttl, 0, clock)
    manager = JwtManager(DefaultJwtEncoder(provider), RecordingDispatcher(), user_id_claim)
    return await manager.create(InMemoryUser(identifier, roles=roles))
