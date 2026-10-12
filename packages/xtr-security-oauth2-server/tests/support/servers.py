"""Building the servers over the in-memory storage the tests use.

The server takes eight things, seven of which every test wants the same: the
three repositories out of :class:`~tests.support.grants.Storage`, a signer over
the minted key, the shared encryption key and a recording dispatcher. This
builds exactly that, so a test names only what it cares about — the clock it
freezes, the response type it wants the answer built by.

The token server beside it is built the same way, out of the same storage and
the same key: what it reads an access token with comes from the provider the
signer holds, so a token one of them issued is one the other recognises.

Nothing here is a double: the repositories really store, the signer really
signs, and the server is the one an application builds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_security_oauth2_server_core.authorization_server import AuthorizationServer
from xtr_security_oauth2_server_core.token_server import TokenServer

from tests.support.encryption import ENCRYPTION_KEY
from tests.support.signing import make_signer

if TYPE_CHECKING:
    from datetime import timedelta

    from xtr_clock import ClockInterface
    from xtr_security_oauth2_server_core.response_types.response_type_interface import (
        ResponseTypeInterface,
    )

    from tests.support.dispatcher import RecordingEventDispatcher
    from tests.support.grants import Storage

__all__ = ["make_server", "make_token_server"]


def make_server(
    storage: Storage,
    dispatcher: RecordingEventDispatcher,
    clock: ClockInterface,
    response_type: ResponseTypeInterface | None = None,
) -> AuthorizationServer:
    """Return a server reading ``storage`` and signing against ``clock``."""
    return AuthorizationServer(
        storage.clients,
        storage.access_tokens,
        storage.scopes,
        make_signer(clock=clock),
        ENCRYPTION_KEY,
        "key",
        dispatcher,
        response_type,
    )


def make_token_server(
    storage: Storage,
    dispatcher: RecordingEventDispatcher,
    clock: ClockInterface,
    audience: str | None = None,
    leeway: timedelta | None = None,
) -> TokenServer:
    """Return a token server reading ``storage`` and judging against ``clock``."""
    signer = make_signer(audience=audience, clock=clock)

    return TokenServer(
        storage.clients,
        storage.access_tokens,
        storage.refresh_tokens,
        signer.jws_provider,
        signer.issuer,
        ENCRYPTION_KEY,
        "key",
        dispatcher,
        clock,
        audience,
        leeway,
    )
