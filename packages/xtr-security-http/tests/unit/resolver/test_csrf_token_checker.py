"""The CSRF token checker vouches for a presented value through the manager."""

from __future__ import annotations

from typing import final

import pytest
from fastapi import HTTPException
from xtr_security_csrf.csrf_token import CsrfToken

from xtr_security_http.decorator.is_csrf_token_valid import IsCsrfTokenValid
from xtr_security_http.resolver.csrf_token_checker import CsrfTokenChecker

pytestmark = pytest.mark.anyio


@final
class VouchingManager:
    """A token manager that vouches for exactly one value, remembering the ids asked."""

    def __init__(self, *, vouched: str | None) -> None:
        self._vouched = vouched
        self.asked_ids: list[str] = []

    async def get_token(self, token_id: str) -> CsrfToken:  # pragma: no cover
        """Not used by the checker; the interface is wider than the check."""
        return CsrfToken(token_id)

    async def refresh_token(self, token_id: str) -> CsrfToken:  # pragma: no cover
        """Not used by the checker; the interface is wider than the check."""
        return CsrfToken(token_id)

    async def remove_token(self, token_id: str) -> str | None:  # pragma: no cover
        """Not used by the checker; the interface is wider than the check."""
        del token_id
        return None

    async def is_token_valid(self, token: CsrfToken) -> bool:
        """Vouch for the value only when it is the one this manager minted."""
        self.asked_ids.append(token.get_id())
        return token.get_value() == self._vouched


def _checker(vouched: str | None) -> CsrfTokenChecker:
    return CsrfTokenChecker(VouchingManager(vouched=vouched))


async def test_it_passes_a_vouched_value() -> None:
    await _checker("s3cret").check(IsCsrfTokenValid("delete_book"), "s3cret")


async def test_it_refuses_a_request_that_presents_no_value() -> None:
    with pytest.raises(HTTPException) as caught:
        await _checker("s3cret").check(IsCsrfTokenValid("delete_book"), None)

    assert caught.value.status_code == 403


async def test_it_refuses_a_value_the_manager_does_not_vouch_for() -> None:
    with pytest.raises(HTTPException) as caught:
        await _checker("s3cret").check(IsCsrfTokenValid("delete_book"), "other")

    assert caught.value.status_code == 403


async def test_it_checks_under_the_marker_token_id() -> None:
    """The manager vouches per id: the check names the marker's id, not a fixed one."""
    manager = VouchingManager(vouched="s3cret")

    await CsrfTokenChecker(manager).check(IsCsrfTokenValid("delete_book"), "s3cret")

    assert manager.asked_ids == ["delete_book"]
