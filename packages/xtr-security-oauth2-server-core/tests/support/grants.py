"""Wiring a grant the way the authorization server wires one.

A grant arrives from its constructor knowing only what it was built with; the
server then hands it the repositories, the signing key, the encryption key and
the default scope before the first request reaches it. These two helpers do
exactly that, so a grant test starts from a grant in the state it is actually
used in, and a missing setter stays a thing a test has to leave out on purpose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.repositories import (
    InMemoryAccessTokenRepository,
    InMemoryAuthCodeRepository,
    InMemoryClientRepository,
    InMemoryDeviceCodeRepository,
    InMemoryRefreshTokenRepository,
    InMemoryScopeRepository,
    InMemoryUserRepository,
)
from tests.support.signing import make_signer

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from xtr_security_oauth2_server_core.grant.grant_type_interface import GrantTypeInterface

__all__ = ["Storage", "wire"]


@final
@dataclass(slots=True)
class Storage:
    """Every repository a grant may be wired with, built fresh together.

    A test that cares about one of them names it — usually the scope
    repository, which has to know the scopes the test asks for — and takes the
    rest as they come.
    """

    clients: InMemoryClientRepository = field(default_factory=InMemoryClientRepository)
    access_tokens: InMemoryAccessTokenRepository = field(
        default_factory=InMemoryAccessTokenRepository,
    )
    auth_codes: InMemoryAuthCodeRepository = field(default_factory=InMemoryAuthCodeRepository)
    refresh_tokens: InMemoryRefreshTokenRepository = field(
        default_factory=InMemoryRefreshTokenRepository,
    )
    scopes: InMemoryScopeRepository = field(default_factory=InMemoryScopeRepository)
    users: InMemoryUserRepository = field(default_factory=InMemoryUserRepository)
    device_codes: InMemoryDeviceCodeRepository = field(
        default_factory=InMemoryDeviceCodeRepository,
    )


def wire(
    grant: GrantTypeInterface,
    storage: Storage,
    clock: ClockInterface | None = None,
    *,
    default_scope: str = "",
) -> None:
    """Hand ``grant`` everything the authorization server hands one.

    The same six calls, in the same order, so a test exercises a grant in the
    state the server leaves it in — and anything the server would set that a
    particular test wants missing has to be left out here on purpose.
    """
    grant.set_client_repository(storage.clients)
    grant.set_access_token_repository(storage.access_tokens)
    grant.set_scope_repository(storage.scopes)
    grant.set_default_scope(default_scope)
    grant.set_private_key(make_signer(clock=clock))
    grant.set_encryption_key(ENCRYPTION_KEY, "key")
