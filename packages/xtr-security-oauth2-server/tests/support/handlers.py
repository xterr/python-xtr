"""Wiring a token handler the way the token server wires one.

A handler arrives from its constructor knowing only the dispatcher and the
clock; the token server then hands it the repositories, the encryption key and
what reads an access token before the first request reaches it. These two
helpers do exactly that, so a handler test starts from a handler in the state
it is actually used in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import make_clock, make_signer
from xtr_security_oauth2_server.authorization_validators.bearer_token_validator import (
    BearerTokenValidator,
)

if TYPE_CHECKING:
    from xtr_clock import ClockInterface

    from tests.support.grants import Storage
    from xtr_security_oauth2_server.handlers.abstract_token_handler import AbstractTokenHandler

__all__ = ["make_validator", "wire_handler"]


def make_validator(storage: Storage, clock: ClockInterface | None = None) -> BearerTokenValidator:
    """Return the reading of an access token the token server builds, over ``storage``."""
    reading = clock if clock is not None else make_clock()
    signer = make_signer(clock=reading)

    return BearerTokenValidator(
        storage.access_tokens,
        signer.jws_provider,
        signer.issuer,
        reading,
    )


def wire_handler(
    handler: AbstractTokenHandler,
    storage: Storage,
    clock: ClockInterface | None = None,
) -> None:
    """Hand ``handler`` everything the token server hands one."""
    handler.set_client_repository(storage.clients)
    handler.set_access_token_repository(storage.access_tokens)
    handler.set_refresh_token_repository(storage.refresh_tokens)
    handler.set_encryption_key(ENCRYPTION_KEY, "key")
    handler.set_bearer_token_validator(make_validator(storage, clock))
