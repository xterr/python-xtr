"""The two kinds of token a client hands to an endpoint, built as this server issues them.

A revocation or introspection request carries a token and nothing else, so a
test of either endpoint has to produce one first: an access token really
signed by the key the tests sign with, and a refresh token really sealed with
the key the tests seal with. Neither is a double — both are read back by the
same code a deployment runs.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Final

from xtr_security_oauth2_server_core.entities.access_token_signer import AccessTokenSigner

from tests.support.encryption import seal
from tests.support.entities import AccessToken, make_client, make_scope
from tests.support.signing import FROZEN_NOW, ISSUER, KEY_ID, make_clock, make_signer

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["AN_HOUR", "A_MONTH", "sealed_refresh_token", "signed_access_token"]

#: How long the tokens these build last, unless a test says otherwise.
AN_HOUR: Final[timedelta] = timedelta(hours=1)
A_MONTH: Final[timedelta] = timedelta(days=30)


def signed_access_token(  # noqa: PLR0917 -- one token, named field by field
    identifier: str = "access-1",
    client_id: str = "client-1",
    user_identifier: str | None = "user-1",
    scope: str = "read",
    lifetime: timedelta = AN_HOUR,
    issuer: str = ISSUER,
    now: datetime = FROZEN_NOW,
) -> str:
    """Return an access token this server would have issued, signed for real."""
    token = AccessToken()
    token.set_identifier(identifier)
    token.set_client(make_client(client_id))
    if user_identifier is not None:
        token.set_user_identifier(user_identifier)
    token.add_scope(make_scope(scope))
    token.set_expiry_date_time(now + lifetime)
    signer = make_signer(clock=make_clock(now))
    token.set_private_key(
        signer
        if issuer == ISSUER
        else AccessTokenSigner(signer.jws_provider, KEY_ID, issuer, make_clock(now)),
    )

    return token.to_string()


def sealed_refresh_token(
    identifier: str = "refresh-1",
    client_id: str = "client-1",
    access_token_id: str | None = "access-1",  # noqa: S107 -- a token's name, not a secret
    lifetime: timedelta = A_MONTH,
    now: datetime = FROZEN_NOW,
) -> str:
    """Return a refresh token this server would have issued, sealed for real."""
    payload: dict[str, object] = {
        "client_id": client_id,
        "refresh_token_id": identifier,
        "scopes": ["read"],
        "user_id": "user-1",
        "expire_time": int((now + lifetime).timestamp()),
    }
    if access_token_id is not None:
        payload["access_token_id"] = access_token_id

    return seal(payload)
