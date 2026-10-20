"""The back-channel logout handler answers the status the pushed token amounts to."""

from __future__ import annotations

from typing import final

import pytest
from xtr_http_kernel.bridge import Response
from xtr_security_core.exception import AuthenticationError

from xtr_security.oidc_back_channel_logout_handler import OidcBackChannelLogoutHandler

pytestmark = pytest.mark.anyio


@final
class _RecordingLogout:
    """A stand-in back-channel logout recording the tokens it is handed."""

    def __init__(self, refusal: str | None = None) -> None:
        self.tokens: list[str] = []
        self._refusal = refusal

    async def logout(self, logout_token: str) -> None:
        """Record the token, or refuse it the way a failed verification does."""
        self.tokens.append(logout_token)
        if self._refusal is not None:
            raise AuthenticationError(self._refusal)


async def test_a_missing_token_is_a_bad_request() -> None:
    logout = _RecordingLogout()
    handler = OidcBackChannelLogoutHandler(logout)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    response = await handler(None)

    assert isinstance(response, Response)
    assert response.get_status_code() == 400
    assert logout.tokens == []


async def test_an_empty_token_is_a_bad_request() -> None:
    logout = _RecordingLogout()
    handler = OidcBackChannelLogoutHandler(logout)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    response = await handler("")

    assert response.get_status_code() == 400
    assert logout.tokens == []


async def test_a_refused_token_is_a_bare_bad_request() -> None:
    logout = _RecordingLogout(refusal="The logout token could not be verified.")
    handler = OidcBackChannelLogoutHandler(logout)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    response = await handler("a-pushed-token")

    assert response.get_status_code() == 400
    assert logout.tokens == ["a-pushed-token"]


async def test_a_verified_token_is_acknowledged() -> None:
    logout = _RecordingLogout()
    handler = OidcBackChannelLogoutHandler(logout)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]

    response = await handler("a-pushed-token")

    assert response.get_status_code() == 200
    assert logout.tokens == ["a-pushed-token"]
